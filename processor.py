#!/usr/bin/env python3
"""
UVR Audio Processor Consumer
Consumes tasks from Redis priority queue, performs audio separation, and sends results
"""

import os
import json
import logging
import time
import signal
import sys
import requests
import tempfile
from audio_separator.separator import Separator
import config
from redis_queue import create_redis_client, RedisPriorityQueue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UVRProcessor:
    """UVR audio separation processor with graceful shutdown"""

    def __init__(self):
        """Initialize UVR processor with model loaded once"""
        self.separator = None
        self.redis_client = None
        self.task_queue = None
        self.result_queue = None
        self.shutdown_flag = False

        # 注册信号处理器用于优雅关闭
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._load_model()
        self._connect_redis()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.shutdown_flag = True

    def _check_gpu_support(self):
        """Check if GPU/CUDA is available"""
        import platform

        is_linux = platform.system() == 'Linux'
        cuda_available = False
        gpu_info = "CPU only"

        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()

            if 'CUDAExecutionProvider' in providers:
                cuda_available = True
                gpu_info = "CUDA available"
                logger.info("✓ CUDA Execution Provider detected")
            elif 'TensorrtExecutionProvider' in providers:
                cuda_available = True
                gpu_info = "TensorRT available"
                logger.info("✓ TensorRT Execution Provider detected")
            else:
                logger.info("GPU providers not available, using CPU")
        except Exception as e:
            logger.warning(f"Failed to check GPU support: {e}")

        return is_linux and cuda_available, gpu_info

    def _load_model(self):
        """Load UVR model - called once on startup (with GPU optimization if available)"""
        try:
            logger.info(f"Loading UVR model: {config.MODEL_NAME}")
            logger.info(f"Model directory: {config.MODEL_FILE_DIR}")

            # Check GPU support
            use_gpu, gpu_info = self._check_gpu_support()
            logger.info(f"Hardware acceleration: {gpu_info}")

            # Configure Separator
            # Note: audio-separator automatically uses GPU if onnxruntime-gpu is installed
            # and CUDAExecutionProvider is available. No explicit parameter needed.
            separator_kwargs = {
                'log_level': logging.INFO,
                'model_file_dir': config.MODEL_FILE_DIR,
                'output_dir': config.OUTPUT_DIR
            }

            if use_gpu:
                logger.info("🚀 GPU acceleration will be used automatically (onnxruntime-gpu detected)")
            else:
                logger.info("Running on CPU mode")

            self.separator = Separator(**separator_kwargs)

            # 确保模型名称包含 .onnx 扩展名
            model_filename = config.MODEL_NAME
            if not model_filename.endswith('.onnx'):
                model_filename = f"{model_filename}.onnx"

            # 检查模型文件是否存在
            model_path = os.path.join(config.MODEL_FILE_DIR, model_filename)
            if not os.path.exists(model_path):
                logger.warning(f"Model file not found: {model_path}")
                logger.info("Attempting to download model automatically...")
                # audio-separator 会自动下载模型

            # Load the specific model
            self.separator.load_model(model_filename)

            if use_gpu:
                logger.info("✅ UVR model loaded successfully with GPU acceleration")
            else:
                logger.info("✅ UVR model loaded successfully (CPU mode)")

        except Exception as e:
            logger.error(f"Failed to load UVR model: {str(e)}")
            logger.error(f"Please ensure model exists at: {config.MODEL_FILE_DIR}/{config.MODEL_NAME}.onnx")
            logger.error(f"You can download it using: python3 download_models.py")
            raise

    def _connect_redis(self):
        """Initialize Redis client and priority queues"""
        try:
            # Create Redis client
            self.redis_client = create_redis_client(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD
            )

            # Initialize priority queues
            self.task_queue = RedisPriorityQueue(self.redis_client, config.REDIS_TASK_QUEUE)
            self.result_queue = RedisPriorityQueue(self.redis_client, config.REDIS_RESULT_QUEUE)

            logger.info("Redis connections and queues initialized")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    # 下载功能已移到 API 层，此方法不再需要
    # def _download_audio(self, audio_url, task_uuid):
    #     已移至 app.py 的 download_audio() 函数

    def _separate_audio(self, input_path, task_uuid):
        """Perform audio separation using UVR"""
        try:
            logger.info(f"[{task_uuid}] Starting audio separation")

            # Perform separation
            output_files = self.separator.separate(input_path)

            logger.info(f"[{task_uuid}] Separation complete. Output files: {output_files}")

            # Find vocals and instrumental files
            vocals_path = None
            instrumental_path = None

            for file_path in output_files:
                # 确保使用完整路径
                # audio-separator 返回的可能是相对路径或文件名
                if not os.path.isabs(file_path):
                    # 如果是相对路径，组合输出目录
                    full_path = os.path.join(config.OUTPUT_DIR, file_path)
                    if not os.path.exists(full_path):
                        # 尝试直接使用返回的路径
                        full_path = file_path
                else:
                    full_path = file_path

                # 检查文件名判断类型
                filename = os.path.basename(full_path).lower()
                if 'vocals' in filename or 'voice' in filename:
                    vocals_path = full_path
                elif 'instrumental' in filename or 'inst' in filename:
                    instrumental_path = full_path

            # If not found by name, use order
            if not vocals_path and len(output_files) > 0:
                vocals_path = output_files[0]
                if not os.path.isabs(vocals_path):
                    vocals_path = os.path.join(config.OUTPUT_DIR, vocals_path)

            if not instrumental_path and len(output_files) > 1:
                instrumental_path = output_files[1]
                if not os.path.isabs(instrumental_path):
                    instrumental_path = os.path.join(config.OUTPUT_DIR, instrumental_path)

            # 验证文件存在
            if not vocals_path or not os.path.exists(vocals_path):
                raise Exception(f"Vocals file not found: {vocals_path}")
            if not instrumental_path or not os.path.exists(instrumental_path):
                raise Exception(f"Instrumental file not found: {instrumental_path}")

            logger.info(f"[{task_uuid}] Vocals: {vocals_path}")
            logger.info(f"[{task_uuid}] Instrumental: {instrumental_path}")

            return vocals_path, instrumental_path

        except Exception as e:
            logger.error(f"[{task_uuid}] Separation failed: {str(e)}")
            raise

    def _process_task(self, task_data):
        """Process a single task"""
        task_uuid = task_data['task_uuid']
        audio_path = task_data['audio_path']  # 改为直接使用本地路径
        hook_url = task_data['hook_url']
        priority = task_data.get('priority', config.DEFAULT_PRIORITY)

        vocals_path = None
        instrumental_path = None

        try:
            logger.info(f"[{task_uuid}] Processing task with priority {priority}")
            logger.info(f"[{task_uuid}] Audio file: {audio_path}")

            # 验证音频文件存在
            if not os.path.exists(audio_path):
                raise Exception(f"Audio file not found: {audio_path}")

            # Separate audio (直接使用已下载的文件)
            vocals_path, instrumental_path = self._separate_audio(audio_path, task_uuid)

            # Send success result to result queue with same priority
            result = {
                'task_uuid': task_uuid,
                'success': True,
                'vocals_path': vocals_path,
                'instrumental_path': instrumental_path,
                'hook_url': hook_url,
                'priority': priority
            }

            self.result_queue.enqueue(result, priority=priority)
            logger.info(f"[{task_uuid}] Success result sent to result queue with priority {priority}")

        except Exception as e:
            logger.error(f"[{task_uuid}] Task processing failed: {str(e)}")

            # Send failure result with same priority
            result = {
                'task_uuid': task_uuid,
                'success': False,
                'error_message': str(e),
                'hook_url': hook_url,
                'priority': priority
            }

            self.result_queue.enqueue(result, priority=priority)
            logger.info(f"[{task_uuid}] Failure result sent to result queue with priority {priority}")

        finally:
            # Clean up input file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.info(f"[{task_uuid}] Cleaned up input file")
                except Exception as e:
                    logger.warning(f"[{task_uuid}] Failed to cleanup input file: {e}")

    def start(self):
        """Start consuming and processing tasks"""
        logger.info("UVR Processor started, waiting for tasks from Redis priority queue...")

        consecutive_errors = 0
        max_consecutive_errors = 10

        try:
            while not self.shutdown_flag:
                try:
                    # Blocking dequeue with 5 second timeout
                    task_data = self.task_queue.dequeue(timeout=5)

                    if task_data is None:
                        consecutive_errors = 0  # 重置错误计数
                        continue  # No task available, continue polling

                    task_uuid = task_data.get('task_uuid', 'unknown')
                    priority = task_data.get('priority', config.DEFAULT_PRIORITY)
                    logger.info(f"Received task: {task_uuid} with priority {priority}")

                    try:
                        # 处理任务
                        self._process_task(task_data)
                        logger.info(f"[{task_uuid}] Task completed successfully")
                        consecutive_errors = 0  # 重置错误计数

                    except Exception as e:
                        logger.error(f"Error processing task {task_uuid}: {str(e)}")
                        # 任务已经从队列中移除，错误已在 _process_task 中处理

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Redis processor error ({consecutive_errors}/{max_consecutive_errors}): {e}")

                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical(f"Too many consecutive errors ({consecutive_errors}), stopping processor")
                        break

                    # 根据错误次数调整休眠时间
                    sleep_time = min(consecutive_errors * 2, 30)  # 最多休眠30秒
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            if not self.shutdown_flag:
                logger.error(f"Processor error: {str(e)}")
                raise
        finally:
            logger.info("Processor shutting down...")
            self.close()

    def close(self):
        """Close connections gracefully"""
        logger.info("Closing Redis connections...")

        # 关闭 Redis client
        if self.redis_client:
            try:
                logger.info("Closing Redis client...")
                self.redis_client.close()
                logger.info("Redis client closed")
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")

        logger.info("Processor shutdown complete")

if __name__ == '__main__':
    processor = UVRProcessor()
    processor.start()

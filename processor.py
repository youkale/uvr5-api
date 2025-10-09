#!/usr/bin/env python3
"""
UVR Audio Processor Consumer
Consumes tasks from Kafka, performs audio separation, and sends results
"""

import os
import json
import logging
import time
import requests
import tempfile
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from audio_separator.separator import Separator
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UVRProcessor:
    """UVR audio separation processor"""

    def __init__(self):
        """Initialize UVR processor with model loaded once"""
        self.separator = None
        self._load_model()
        self.consumer = None
        self.producer = None
        self._connect_kafka()

    def _load_model(self):
        """Load UVR model - called once on startup"""
        try:
            logger.info(f"Loading UVR model: {config.MODEL_NAME}")
            logger.info(f"Model directory: {config.MODEL_FILE_DIR}")

            self.separator = Separator(
                log_level=logging.INFO,
                model_file_dir=config.MODEL_FILE_DIR,
                output_dir=config.OUTPUT_DIR
            )

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
            logger.info("UVR model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load UVR model: {str(e)}")
            logger.error(f"Please ensure model exists at: {config.MODEL_FILE_DIR}/{config.MODEL_NAME}.onnx")
            logger.error(f"You can download it using: python3 download_models.py")
            raise

    def _connect_kafka(self):
        """Initialize Kafka consumer and producer"""
        try:
            # Consumer for tasks
            self.consumer = KafkaConsumer(
                config.KAFKA_TASK_TOPIC,
                bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','),
                group_id=config.KAFKA_PROCESSOR_GROUP_ID,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',
                enable_auto_commit=False,  # 手动提交，确保处理完成后才提交
                max_poll_records=1,  # 每次只读取1条消息
                max_poll_interval_ms=300000
            )

            # Producer for results
            self.producer = KafkaProducer(
                bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                retries=3,
                acks='all'
            )

            logger.info("Kafka connections established")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            raise

    def _download_audio(self, audio_url, task_uuid):
        """
        Download audio from URL to local temporary file
        Based on: https://raw.githubusercontent.com/youkale/index-tts/refs/heads/main/api_server.py
        """
        try:
            logger.info(f"[{task_uuid}] Downloading audio from URL: {audio_url}")
            start_time = time.time()

            # Create temp file in temp directory
            # Keep original extension if available, default to .wav
            ext = os.path.splitext(audio_url.split('?')[0])[1] or '.wav'
            filename = f"{task_uuid}_input{ext}"
            local_path = os.path.join(config.TEMP_DIR, filename)

            # Download the file with streaming and timeout
            response = requests.get(audio_url, timeout=30, stream=True)
            response.raise_for_status()

            # Check content type to ensure it's audio
            content_type = response.headers.get('content-type', '')
            if not any(audio_type in content_type.lower() for audio_type in ['audio', 'wav', 'mp3', 'flac', 'ogg', 'm4a', 'aac']):
                logger.warning(f"[{task_uuid}] Downloaded file may not be audio: {content_type}")

            # Get file size for progress tracking
            total_size = int(response.headers.get('content-length', 0))
            if total_size > 0:
                total_mb = total_size / (1024 * 1024)
                logger.info(f"[{task_uuid}] File size: {total_mb:.2f} MB")

            # Save to local file with progress tracking
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB chunks
            last_log_time = start_time

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Log progress every 2 seconds
                        current_time = time.time()
                        if total_size > 0 and (current_time - last_log_time) >= 2:
                            percent = (downloaded / total_size) * 100
                            speed = downloaded / (current_time - start_time) / (1024 * 1024)  # MB/s
                            logger.info(f"[{task_uuid}] Download progress: {percent:.1f}% ({speed:.2f} MB/s)")
                            last_log_time = current_time

            # Verify download
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                elapsed = time.time() - start_time
                speed = file_size / elapsed / (1024 * 1024) if elapsed > 0 else 0

                logger.info(f"[{task_uuid}] Audio downloaded to: {local_path}")
                logger.info(f"[{task_uuid}] Download completed in {elapsed:.1f}s (avg {speed:.2f} MB/s)")

                return local_path
            else:
                raise Exception("Downloaded file not found")

        except requests.exceptions.Timeout:
            logger.error(f"[{task_uuid}] Download timeout: {audio_url}")
            raise Exception(f"Download timeout after 30 seconds")
        except requests.exceptions.HTTPError as e:
            logger.error(f"[{task_uuid}] HTTP error downloading audio: {e}")
            raise Exception(f"HTTP error: {e.response.status_code if e.response else 'unknown'}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[{task_uuid}] Network error downloading audio: {e}")
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"[{task_uuid}] Failed to download audio: {str(e)}")
            # Clean up partial file
            if 'local_path' in locals() and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    logger.info(f"[{task_uuid}] Cleaned up partial download")
                except:
                    pass
            raise

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
        audio_url = task_data['audio_url']
        hook_url = task_data['hook_url']

        input_path = None
        vocals_path = None
        instrumental_path = None

        try:
            logger.info(f"[{task_uuid}] Processing task")

            # Download audio
            input_path = self._download_audio(audio_url, task_uuid)

            # Separate audio
            vocals_path, instrumental_path = self._separate_audio(input_path, task_uuid)

            # Send success result to result topic
            result = {
                'task_uuid': task_uuid,
                'success': True,
                'vocals_path': vocals_path,
                'instrumental_path': instrumental_path,
                'hook_url': hook_url
            }

            self.producer.send(config.KAFKA_RESULT_TOPIC, key=task_uuid, value=result)
            logger.info(f"[{task_uuid}] Success result sent to result topic")

        except Exception as e:
            logger.error(f"[{task_uuid}] Task processing failed: {str(e)}")

            # Send failure result
            result = {
                'task_uuid': task_uuid,
                'success': False,
                'error_message': str(e),
                'hook_url': hook_url
            }

            self.producer.send(config.KAFKA_RESULT_TOPIC, key=task_uuid, value=result)
            logger.info(f"[{task_uuid}] Failure result sent to result topic")

        finally:
            # Clean up input file
            if input_path and os.path.exists(input_path):
                try:
                    os.remove(input_path)
                    logger.info(f"[{task_uuid}] Cleaned up input file")
                except Exception as e:
                    logger.warning(f"[{task_uuid}] Failed to cleanup input file: {e}")

    def start(self):
        """Start consuming and processing tasks"""
        logger.info("UVR Processor started, waiting for tasks...")

        try:
            for message in self.consumer:
                try:
                    task_data = message.value
                    task_uuid = task_data.get('task_uuid', 'unknown')
                    logger.info(f"Received task: {task_uuid}")

                    # 处理任务
                    self._process_task(task_data)

                    # 处理成功后手动提交 offset
                    self.consumer.commit()
                    logger.info(f"[{task_uuid}] Offset committed successfully")

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    # 即使处理失败也提交 offset，避免重复处理
                    # 如果不想跳过失败的消息，可以不提交或实现重试逻辑
                    try:
                        self.consumer.commit()
                        logger.warning(f"Offset committed despite error (message will not be retried)")
                    except Exception as commit_error:
                        logger.error(f"Failed to commit offset: {commit_error}")
                    continue

        except KeyboardInterrupt:
            logger.info("Processor interrupted by user")
        except Exception as e:
            logger.error(f"Processor error: {str(e)}")
            raise
        finally:
            self.close()

    def close(self):
        """Close connections"""
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()
        logger.info("Processor connections closed")

if __name__ == '__main__':
    processor = UVRProcessor()
    processor.start()

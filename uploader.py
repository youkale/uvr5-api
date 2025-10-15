#!/usr/bin/env python3
"""
S3 Uploader and Webhook Notifier
Consumes results from Redis priority queue, uploads to S3, and sends webhook callbacks
"""

import os
import json
import logging
import time
import signal
import sys
import requests
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import config
from redis_queue import create_redis_client, RedisPriorityQueue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class S3Uploader:
    """S3 uploader and webhook notifier with graceful shutdown"""

    def __init__(self):
        """Initialize S3 client and Redis consumer"""
        self.s3_client = None
        self.redis_client = None
        self.result_queue = None
        self.shutdown_flag = False

        # 注册信号处理器用于优雅关闭
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._init_s3()
        self._connect_redis()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.shutdown_flag = True

    def _init_s3(self):
        """Initialize S3-compatible client (支持 AWS S3, Cloudflare R2, MinIO 等)"""
        try:
            if not all([config.AWS_ACCESS_KEY_ID, config.AWS_SECRET_ACCESS_KEY, config.S3_BUCKET_NAME]):
                raise ValueError("S3 credentials and bucket name must be configured")

            # 创建 S3 客户端配置
            s3_config = {
                'aws_access_key_id': config.AWS_ACCESS_KEY_ID,
                'aws_secret_access_key': config.AWS_SECRET_ACCESS_KEY,
                'region_name': config.AWS_REGION
            }

            # 如果配置了自定义 endpoint（如 Cloudflare R2, MinIO），则使用它
            if config.S3_ENDPOINT_URL:
                s3_config['endpoint_url'] = config.S3_ENDPOINT_URL
                logger.info(f"Using S3-compatible endpoint: {config.S3_ENDPOINT_URL}")

            self.s3_client = boto3.client('s3', **s3_config)

            # Test connection
            self.s3_client.head_bucket(Bucket=config.S3_BUCKET_NAME)
            logger.info(f"S3 client initialized for bucket: {config.S3_BUCKET_NAME}")

        except NoCredentialsError:
            logger.error("S3 credentials not found")
            raise
        except ClientError as e:
            logger.error(f"S3 initialization failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected S3 error: {str(e)}")
            raise

    def _connect_redis(self):
        """Initialize Redis client and result queue"""
        try:
            # Create Redis client
            self.redis_client = create_redis_client(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD
            )

            # Initialize result queue
            self.result_queue = RedisPriorityQueue(self.redis_client, config.REDIS_RESULT_QUEUE)

            logger.info("Redis client and result queue initialized")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    def _generate_s3_url(self, s3_key):
        """
        生成 S3 文件的公共访问 URL
        参考 https://github.com/youkale/index-tts/blob/main/api_server.py

        支持：
        1. 自定义公共域名（如 Cloudflare R2 的 public.r2.dev）
        2. S3 endpoint URL（如 R2, MinIO）
        3. 标准 AWS S3 URL
        """
        # 优先使用自定义公共域名
        if config.S3_PUBLIC_DOMAIN:
            return f"{config.S3_PUBLIC_DOMAIN}/{s3_key}"

        # 使用 endpoint URL（用于 R2, MinIO 等）
        if config.S3_ENDPOINT_URL:
            endpoint = config.S3_ENDPOINT_URL.rstrip('/')
            return f"{endpoint}/{config.S3_BUCKET_NAME}/{s3_key}"

        # 默认使用标准 AWS S3 URL
        return f"https://{config.S3_BUCKET_NAME}.s3.{config.AWS_REGION}.amazonaws.com/{s3_key}"

    def _upload_to_s3(self, file_path, s3_key, max_retries=3):
        """
        Upload file to S3-compatible storage with retry logic

        Args:
            file_path: Local file path
            s3_key: S3 object key
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            str: Public URL of uploaded file
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Uploading {file_path} to S3 as {s3_key} (attempt {attempt + 1}/{max_retries})")

                # 上传文件配置
                extra_args = {'ContentType': 'audio/wav'}

                # 某些 S3 兼容服务（如 R2）不支持 ACL，需要通过 bucket 策略设置公共访问
                try:
                    extra_args['ACL'] = 'public-read'
                except Exception:
                    if attempt == 0:  # Only log once
                        logger.info("ACL not supported, using bucket policy for public access")

                self.s3_client.upload_file(
                    file_path,
                    config.S3_BUCKET_NAME,
                    s3_key,
                    ExtraArgs=extra_args
                )

                # 生成公共访问 URL
                url = self._generate_s3_url(s3_key)

                logger.info(f"File uploaded successfully: {url}")
                return url

            except ClientError as e:
                last_error = e
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                logger.warning(f"S3 upload failed (attempt {attempt + 1}/{max_retries}): {error_code} - {str(e)}")

                # 某些错误不值得重试（如权限错误、bucket不存在等）
                non_retryable_errors = ['NoSuchBucket', 'AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']
                if error_code in non_retryable_errors:
                    logger.error(f"Non-retryable S3 error: {error_code}")
                    raise

                if attempt < max_retries - 1:
                    sleep_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)

            except Exception as e:
                last_error = e
                logger.warning(f"Unexpected upload error (attempt {attempt + 1}/{max_retries}): {str(e)}")

                if attempt < max_retries - 1:
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)

        # All retries failed
        logger.error(f"All {max_retries} upload attempts failed for {s3_key}")
        raise last_error if last_error else Exception("S3 upload failed")

    def _send_webhook(self, hook_url, payload, max_retries=3):
        """Send webhook with retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending webhook to {hook_url} (attempt {attempt + 1})")

                response = requests.post(
                    hook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                response.raise_for_status()
                logger.info(f"Webhook sent successfully: {hook_url}")
                return

            except requests.exceptions.RequestException as e:
                logger.warning(f"Webhook failed (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All webhook attempts failed for {hook_url}")
                    raise

    def _cleanup_files(self, *file_paths):
        """Clean up local files"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {file_path}: {e}")

    def _process_success_result(self, result):
        """
        Process successful separation result

        流程：
        1. 上传文件到S3（带重试）
        2. 发送webhook回调（带重试）
        3. 清理本地文件

        注意：任务已从队列移除，即使失败也不会重新入队，避免重复上传
        """
        task_uuid = result['task_uuid']
        vocals_path = result['vocals_path']
        instrumental_path = result['instrumental_path']
        hook_url = result['hook_url']
        priority = result.get('priority', config.DEFAULT_PRIORITY)

        vocals_url = None
        instrumental_url = None
        upload_success = False

        try:
            logger.info(f"[{task_uuid}] Processing success result (priority: {priority})")

            # Step 1: Upload vocals to S3 (with retry)
            vocals_s3_key = f"{task_uuid}_vocals.wav"
            vocals_url = self._upload_to_s3(vocals_path, vocals_s3_key, max_retries=3)

            # Step 2: Upload instrumental to S3 (with retry)
            instrumental_s3_key = f"{task_uuid}_instrumental.wav"
            instrumental_url = self._upload_to_s3(instrumental_path, instrumental_s3_key, max_retries=3)

            upload_success = True
            logger.info(f"[{task_uuid}] Both files uploaded to S3 successfully")

            # Step 3: Send success callback (with retry)
            callback_payload = {
                'task_uuid': task_uuid,
                'status': 'success',
                'timestamp': int(time.time()),
                'vocals': vocals_url,
                'instrumental': instrumental_url
            }

            try:
                self._send_webhook(hook_url, callback_payload)
                logger.info(f"[{task_uuid}] Success callback sent")
            except Exception as webhook_error:
                # Webhook失败但S3已上传成功
                # 不应该抛出异常导致发送failure回调，因为文件已经成功上传
                logger.error(f"[{task_uuid}] Webhook failed but files are uploaded to S3: {str(webhook_error)}")
                logger.error(f"[{task_uuid}] Files available at: vocals={vocals_url}, instrumental={instrumental_url}")
                # 不重新抛出异常，避免发送错误的failure回调

        except Exception as e:
            logger.error(f"[{task_uuid}] Failed to process success result: {str(e)}")

            # 只有在上传失败时才发送failure回调
            if not upload_success:
                logger.info(f"[{task_uuid}] S3 upload failed, sending failure callback")
                try:
                    self._send_failure_callback(task_uuid, hook_url, f"S3 upload failed: {str(e)}")
                except Exception as callback_error:
                    logger.error(f"[{task_uuid}] Failed to send failure callback: {str(callback_error)}")
            else:
                # 上传成功但其他步骤失败（这种情况已在上面的webhook异常处理中覆盖）
                logger.error(f"[{task_uuid}] Files uploaded but post-processing failed: {str(e)}")

        finally:
            # Step 4: Clean up local files (always execute)
            # 无论成功失败都清理本地文件，避免磁盘空间占用
            self._cleanup_files(vocals_path, instrumental_path)
            logger.info(f"[{task_uuid}] Result processing completed")

    def _send_failure_callback(self, task_uuid, hook_url, error_message):
        """Send failure callback"""
        try:
            callback_payload = {
                'task_uuid': task_uuid,
                'status': 'failed',
                'timestamp': int(time.time()),
                'error_message': error_message
            }

            self._send_webhook(hook_url, callback_payload)
            logger.info(f"[{task_uuid}] Failure callback sent")

        except Exception as e:
            logger.error(f"[{task_uuid}] Failed to send failure callback: {str(e)}")

    def _process_failure_result(self, result):
        """Process failed separation result"""
        task_uuid = result['task_uuid']
        error_message = result.get('error_message', 'Unknown error')
        hook_url = result['hook_url']
        priority = result.get('priority', config.DEFAULT_PRIORITY)

        logger.info(f"[{task_uuid}] Processing failure result (priority: {priority})")
        self._send_failure_callback(task_uuid, hook_url, error_message)

    def start(self):
        """Start consuming results and uploading"""
        logger.info("S3 Uploader started, waiting for results from Redis priority queue...")

        consecutive_errors = 0
        max_consecutive_errors = 10

        try:
            while not self.shutdown_flag:
                try:
                    # Blocking dequeue with 5 second timeout
                    result = self.result_queue.dequeue(timeout=5)

                    if result is None:
                        consecutive_errors = 0  # 重置错误计数
                        continue  # No result available, continue polling

                    task_uuid = result.get('task_uuid', 'unknown')
                    success = result.get('success', False)
                    priority = result.get('priority', config.DEFAULT_PRIORITY)

                    logger.info(f"Received result: {task_uuid} (success: {success}, priority: {priority})")

                    try:
                        if success:
                            self._process_success_result(result)
                        else:
                            self._process_failure_result(result)

                        logger.info(f"[{task_uuid}] Result processed successfully")
                        consecutive_errors = 0  # 重置错误计数

                    except Exception as e:
                        logger.error(f"Error processing result {task_uuid}: {str(e)}")
                        # 任务已经从队列中移除

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Redis uploader error ({consecutive_errors}/{max_consecutive_errors}): {e}")

                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical(f"Too many consecutive errors ({consecutive_errors}), stopping uploader")
                        break

                    # 根据错误次数调整休眠时间
                    sleep_time = min(consecutive_errors * 2, 30)  # 最多休眠30秒
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            if not self.shutdown_flag:
                logger.error(f"Uploader error: {str(e)}")
                raise
        finally:
            logger.info("Uploader shutting down...")
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

        logger.info("Uploader shutdown complete")

if __name__ == '__main__':
    uploader = S3Uploader()
    uploader.start()

#!/usr/bin/env python3
"""
S3 Uploader and Webhook Notifier
Consumes results from Kafka, uploads to S3, and sends webhook callbacks
"""

import os
import json
import logging
import time
import requests
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from kafka import KafkaConsumer
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class S3Uploader:
    """S3 uploader and webhook notifier"""

    def __init__(self):
        """Initialize S3 client and Kafka consumer"""
        self.s3_client = None
        self.consumer = None
        self._init_s3()
        self._connect_kafka()

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

    def _connect_kafka(self):
        """Initialize Kafka consumer for results"""
        try:
            self.consumer = KafkaConsumer(
                config.KAFKA_RESULT_TOPIC,
                bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','),
                group_id=config.KAFKA_UPLOADER_GROUP_ID,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',
                enable_auto_commit=False,  # 手动提交
                max_poll_records=1,  # 每次只读取1条消息
                max_poll_interval_ms=50000
            )

            logger.info("Kafka consumer connected for results")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
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

    def _upload_to_s3(self, file_path, s3_key):
        """Upload file to S3-compatible storage and return public URL"""
        try:
            logger.info(f"Uploading {file_path} to S3 as {s3_key}")

            # 上传文件配置
            extra_args = {'ContentType': 'audio/wav'}

            # 某些 S3 兼容服务（如 R2）不支持 ACL，需要通过 bucket 策略设置公共访问
            try:
                extra_args['ACL'] = 'public-read'
            except Exception:
                logger.info("ACL not supported, using bucket policy for public access")

            self.s3_client.upload_file(
                file_path,
                config.S3_BUCKET_NAME,
                s3_key,
                ExtraArgs=extra_args
            )

            # 生成公共访问 URL
            url = self._generate_s3_url(s3_key)

            logger.info(f"File uploaded: {url}")
            return url

        except ClientError as e:
            logger.error(f"S3 upload failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected upload error: {str(e)}")
            raise

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
        """Process successful separation result"""
        task_uuid = result['task_uuid']
        vocals_path = result['vocals_path']
        instrumental_path = result['instrumental_path']
        hook_url = result['hook_url']

        try:
            logger.info(f"[{task_uuid}] Processing success result")

            # Upload vocals to S3
            vocals_s3_key = f"{task_uuid}_vocals.wav"
            vocals_url = self._upload_to_s3(vocals_path, vocals_s3_key)

            # Upload instrumental to S3
            instrumental_s3_key = f"{task_uuid}_instrumental.wav"
            instrumental_url = self._upload_to_s3(instrumental_path, instrumental_s3_key)

            # Send success callback
            callback_payload = {
                'task_uuid': task_uuid,
                'status': 'success',
                'timestamp': int(time.time()),
                'vocals': vocals_url,
                'instrumental': instrumental_url
            }

            self._send_webhook(hook_url, callback_payload)
            logger.info(f"[{task_uuid}] Success callback sent")

        except Exception as e:
            logger.error(f"[{task_uuid}] Failed to process success result: {str(e)}")

            # Send failure callback
            self._send_failure_callback(task_uuid, hook_url, f"Upload/callback failed: {str(e)}")

        finally:
            # Clean up files
            self._cleanup_files(vocals_path, instrumental_path)

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

        logger.info(f"[{task_uuid}] Processing failure result")
        self._send_failure_callback(task_uuid, hook_url, error_message)

    def start(self):
        """Start consuming results and uploading"""
        logger.info("S3 Uploader started, waiting for results...")

        try:
            for message in self.consumer:
                try:
                    result = message.value
                    task_uuid = result.get('task_uuid', 'unknown')
                    success = result.get('success', False)

                    logger.info(f"Received result: {task_uuid} (success: {success})")

                    if success:
                        self._process_success_result(result)
                    else:
                        self._process_failure_result(result)

                    # 处理完成后手动提交 offset
                    self.consumer.commit()
                    logger.info(f"[{task_uuid}] Offset committed successfully")

                except Exception as e:
                    logger.error(f"Error processing result message: {str(e)}")
                    # 即使失败也提交 offset，避免重复处理
                    try:
                        self.consumer.commit()
                        logger.warning(f"Offset committed despite error (message will not be retried)")
                    except Exception as commit_error:
                        logger.error(f"Failed to commit offset: {commit_error}")
                    continue

        except KeyboardInterrupt:
            logger.info("Uploader interrupted by user")
        except Exception as e:
            logger.error(f"Uploader error: {str(e)}")
            raise
        finally:
            self.close()

    def close(self):
        """Close connections"""
        if self.consumer:
            self.consumer.close()
        logger.info("Uploader connections closed")

if __name__ == '__main__':
    uploader = S3Uploader()
    uploader.start()

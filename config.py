import os
from dotenv import load_dotenv

load_dotenv()

# Basic Auth Configuration
BASIC_AUTH_USERNAME = os.getenv('BASIC_AUTH_USERNAME', 'admin')
BASIC_AUTH_PASSWORD = os.getenv('BASIC_AUTH_PASSWORD', 'password')

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TASK_TOPIC = os.getenv('KAFKA_TASK_TOPIC', 'uvr_tasks')
KAFKA_RESULT_TOPIC = os.getenv('KAFKA_RESULT_TOPIC', 'uvr_results')
KAFKA_PROCESSOR_GROUP_ID = os.getenv('KAFKA_PROCESSOR_GROUP_ID', 'uvr_processor_group')
KAFKA_UPLOADER_GROUP_ID = os.getenv('KAFKA_UPLOADER_GROUP_ID', 'uvr_uploader_group')

# S3-Compatible Storage Configuration (支持 AWS S3, Cloudflare R2, MinIO 等)
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')  # 可选，用于 R2 等 S3 兼容服务
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'auto')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
S3_PUBLIC_DOMAIN = os.getenv('S3_PUBLIC_DOMAIN')  # 自定义公共域名，如 R2 的 public.r2.dev

# API Configuration
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', 8000))

# UVR Model Configuration
MODEL_NAME = os.getenv('MODEL_NAME', 'UVR-MDX-NET-Inst_HQ_4')
MODEL_FILE_DIR = os.getenv('MODEL_FILE_DIR', './models')  # 模型文件存储目录
TEMP_DIR = os.getenv('TEMP_DIR', './temp')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', './output')

# Create directories
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_FILE_DIR, exist_ok=True)

# UVR Audio Separation API Service

基于UVR5框架的音频分离API服务，使用Flask、Redis优先级队列和AWS S3构建的完整异步处理系统。

## 🎯 功能特性

- ✅ 使用 **UVR-MDX-NET-Inst_HQ_4** 模型进行高质量音频分离
- ✅ 基于 **Flask** 的 REST API
- ✅ **Basic Auth** 认证保护
- ✅ **Redis** 优先级队列（支持任务优先级 1-5）
- ✅ 自动上传到 **AWS S3**
- ✅ **Webhook** 回调通知
- ✅ **Docker** 容器化部署
- ✅ 使用 **uv** 进行依赖管理

## 📋 系统架构

```
客户端请求
    ↓
Flask API (认证 + 生成UUID + 优先级)
    ↓
Redis优先级任务队列
    ↓
音频处理器 (下载 + UVR分离)
    ↓
Redis优先级结果队列
    ↓
S3上传器 (上传 + Webhook回调)
    ↓
清理临时文件
```

### 优先级队列说明

- 使用 Redis ZSet 实现优先级队列
- 优先级范围：1-5（1=最低优先级，5=最高优先级，默认=3）
- 分数计算：`timestamp * (6 - priority)`，分数越低优先级越高
- 支持阻塞式获取任务，保证按优先级顺序处理

## 🚀 快速开始

### 前置要求

**Docker 模式：**
- Docker & Docker Compose

**本地运行模式：**
- Python 3.11+
- Redis 服务
- (推荐) uv 包管理器

---

### 方式一：使用 Docker（推荐）

#### 0. 下载模型（可选，首次运行会自动下载）

```bash
# 下载默认模型
python3 download_models.py

# 查看所有可用模型
python3 download_models.py --list
```

详细说明请查看：[MODELS.md](MODELS.md)

#### 1. 配置环境变量

复制环境变量模板：

```bash
cp env.example .env
```

编辑 `.env` 文件，配置以下关键信息：

```bash
# Basic Auth 认证
BASIC_AUTH_USERNAME=admin
BASIC_AUTH_PASSWORD=your_secure_password

# AWS S3 配置
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=your-bucket-name
S3_BASE_URL=https://your-bucket-name.s3.amazonaws.com
```

#### 2. 启动服务

```bash
./start.sh
```

服务将自动：
- 启动 Redis 服务
- 启动 Flask API 服务器
- 启动音频处理器
- 启动 S3 上传服务

#### 3. 测试API

```bash
./test_api.sh
```

或使用 curl：

```bash
curl -u admin:password http://localhost:8000/health
```

#### 4. 停止服务

```bash
./stop.sh
```

---

### 方式二：本地直接运行（不使用 Docker）

#### 1. 启动 Redis

```bash
# 选项 A: 使用 Docker 启动 Redis
docker run -d -p 6379:6379 --name redis redis:latest

# 选项 B: 使用本地 Redis 服务
# 启动你的本地 Redis
redis-server

# 选项 C: 使用 Homebrew (macOS)
brew install redis
brew services start redis
```

#### 2. 配置环境变量

```bash
cp env.example .env
# 编辑 .env 文件
```

#### 3. 一键启动所有服务

```bash
./start_local.sh
```

这个脚本会自动：
- ✅ 检查 Python 和依赖
- ✅ 创建虚拟环境
- ✅ 安装依赖（使用 uv 或 pip）
- ✅ 启动所有服务（后台运行）
- ✅ 显示服务状态

#### 4. 管理服务

```bash
# 查看状态
./status_local.sh

# 停止服务
./stop_local.sh

# 重启服务
./restart_local.sh

# 查看日志
tail -f logs/*.log
```

详细说明请查看：[LOCAL_RUN.md](LOCAL_RUN.md)

---

## 📡 API 接口

### 健康检查

```http
GET /health
```

响应：
```json
{
  "status": "healthy",
  "timestamp": 1759034893
}
```

### 音频分离

```http
POST /generate
Authorization: Basic <credentials>
Content-Type: application/json

{
  "audio": "https://example.com/audio.wav",
  "hook_url": "https://example.com/webhook",
  "priority": 3  // Optional: 1-5, 默认为3 (1=最低, 5=最高)
}
```

响应：
```json
{
  "message": "Task has been queued for processing",
  "status": "queued",
  "task_uuid": "eb98d47d-aad8-4282-b7e4-3cf115a54c40",
  "priority": 3
}
```

## 🔔 Webhook 回调

### 成功回调

```json
{
  "task_uuid": "eb98d47d-aad8-4282-b7e4-3cf115a54c40",
  "status": "success",
  "timestamp": 1759034893,
  "vocals": "https://s3.amazonaws.com/bucket/uuid_vocals.wav",
  "instrumental": "https://s3.amazonaws.com/bucket/uuid_instrumental.wav"
}
```

### 失败回调

```json
{
  "task_uuid": "eb98d47d-aad8-4282-b7e4-3cf115a54c40",
  "status": "failed",
  "timestamp": 1759034893,
  "error_message": "Error description"
}
```

## 🔧 本地开发

### 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 安装依赖

```bash
uv pip install -r pyproject.toml
```

### 运行单个服务

```bash
# API 服务器
python app.py

# 音频处理器
python processor.py

# S3 上传器
python uploader.py
```

## 📦 项目结构

```
uvr_api/
├── app.py              # Flask API 服务器
├── processor.py        # 音频处理消费者
├── uploader.py         # S3 上传和回调服务
├── config.py           # 配置管理
├── redis_queue.py      # Redis 优先级队列抽象
├── pyproject.toml      # Python 依赖
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 镜像
├── docker-compose.yml  # 服务编排
├── start.sh            # 启动脚本
├── stop.sh             # 停止脚本
├── test_api.sh         # API 测试脚本
└── README.md           # 项目文档
```

## 🔍 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务
docker-compose logs -f api
docker-compose logs -f processor
docker-compose logs -f uploader
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `BASIC_AUTH_USERNAME` | API 认证用户名 | `admin` |
| `BASIC_AUTH_PASSWORD` | API 认证密码 | `password` |
| `REDIS_HOST` | Redis 服务器地址 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `REDIS_DB` | Redis 数据库编号 | `0` |
| `REDIS_PASSWORD` | Redis 密码（可选） | - |
| `REDIS_TASK_QUEUE` | 任务队列名称 | `uvr_tasks` |
| `REDIS_RESULT_QUEUE` | 结果队列名称 | `uvr_results` |
| `DEFAULT_PRIORITY` | 默认任务优先级 | `3` |
| `AWS_ACCESS_KEY_ID` | S3 访问密钥 | - |
| `AWS_SECRET_ACCESS_KEY` | S3 密钥 | - |
| `AWS_REGION` | S3 区域 | `auto` |
| `S3_BUCKET_NAME` | S3 存储桶名称 | - |
| `S3_ENDPOINT_URL` | S3 endpoint（R2/MinIO） | - |
| `S3_PUBLIC_DOMAIN` | 自定义公共域名 | - |
| `MODEL_NAME` | UVR 模型名称 | `UVR-MDX-NET-Inst_HQ_4` |

### S3 兼容存储配置

本服务支持多种 S3 兼容存储，包括：

#### 1. AWS S3（标准配置）

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
# 不需要设置 S3_ENDPOINT_URL 和 S3_PUBLIC_DOMAIN
```

#### 2. Cloudflare R2（推荐）

参考 [index-tts 项目实现](https://github.com/youkale/index-tts/blob/main/api_server.py)

```bash
AWS_ACCESS_KEY_ID=your_r2_access_key_id
AWS_SECRET_ACCESS_KEY=your_r2_secret_access_key
AWS_REGION=auto
S3_BUCKET_NAME=your-bucket-name
S3_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
S3_PUBLIC_DOMAIN=https://your-bucket.your-domain.com
```

**R2 配置步骤：**
1. 在 Cloudflare Dashboard 创建 R2 存储桶
2. 生成 API 令牌（获取 Access Key 和 Secret Key）
3. 设置自定义域名或使用 R2.dev 子域
4. 配置存储桶的公共访问权限

#### 3. MinIO（自托管）

```bash
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
S3_ENDPOINT_URL=http://localhost:9000
S3_PUBLIC_DOMAIN=http://localhost:9000/your-bucket-name
```

### UVR 模型

服务使用 `audio-separator` 库，首次运行时会自动下载模型。支持的模型：
- UVR-MDX-NET-Inst_HQ_4 (推荐)
- 其他 UVR 模型

## 🐛 故障排除

### 问题：Redis 连接失败
- 确保 Redis 服务正常运行：`redis-cli ping`
- 检查 `REDIS_HOST` 和 `REDIS_PORT` 配置
- 如果使用密码，确保 `REDIS_PASSWORD` 正确

### 问题：S3 上传失败
- 验证 AWS 凭证是否正确
- 确认 S3 存储桶权限设置
- 检查存储桶是否允许公共读取

### 问题：模型下载失败
- 首次运行需要下载模型（~200MB）
- 确保网络连接正常
- 检查磁盘空间

### 问题：内存不足
- UVR 模型需要至少 4GB RAM
- 考虑增加 Docker 内存限制

## 🔒 安全建议

1. **修改默认密码**：在生产环境中必须修改 Basic Auth 密码
2. **使用 HTTPS**：建议在生产环境使用反向代理（如 Nginx）配置 HTTPS
3. **环境变量保护**：不要将 `.env` 文件提交到版本控制
4. **S3 权限**：仅授予必要的 S3 权限

## 📝 示例请求

### Python

```python
import requests
from requests.auth import HTTPBasicAuth

response = requests.post(
    'http://localhost:8000/generate',
    auth=HTTPBasicAuth('admin', 'password'),
    json={
        'audio': 'https://example.com/audio.wav',
        'hook_url': 'https://example.com/webhook',
        'priority': 5  # Optional: 1-5, 默认为3
    }
)

print(response.json())
```

### cURL

```bash
curl -X POST http://localhost:8000/generate \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "https://example.com/audio.wav",
    "hook_url": "https://example.com/webhook",
    "priority": 5
  }'
```

## 🤝 技术栈

- **Web Framework**: Flask 3.0+
- **Authentication**: Flask-HTTPAuth
- **Message Queue**: Redis (优先级队列)
- **Audio Processing**: audio-separator (UVR5)
- **Cloud Storage**: AWS S3 (boto3)
- **Container**: Docker & Docker Compose
- **Package Manager**: uv

## 🔄 从 Kafka 迁移到 Redis

本项目已从 Kafka 迁移到 Redis 优先级队列。主要变更：

### 主要改进

1. **优先级支持**：支持任务优先级（1-5），高优先级任务优先处理
2. **轻量级**：Redis 比 Kafka 更轻量，部署更简单
3. **更低延迟**：Redis 的响应时间更短
4. **简化部署**：不再需要 Zookeeper 和 Kafka

### 迁移步骤

如果你从旧版本升级：

1. **安装 Redis**
```bash
# Docker
docker run -d -p 6379:6379 --name redis redis:latest

# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
```

2. **更新环境变量**
```bash
# 移除 Kafka 配置
# KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# 添加 Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_TASK_QUEUE=uvr_tasks
REDIS_RESULT_QUEUE=uvr_results
DEFAULT_PRIORITY=3
```

3. **更新依赖**
```bash
pip install -r requirements.txt
# 或
uv pip install -r requirements.txt
```

4. **重启服务**
```bash
./restart_local.sh
```

### API 变更

`/generate` 端点新增可选参数：
- `priority`: 整数，范围 1-5（1=最低，5=最高，默认=3）

示例：
```json
{
  "audio": "https://example.com/audio.wav",
  "hook_url": "https://example.com/webhook",
  "priority": 5
}
```

## 📄 许可证

本项目仅供学习和研究使用。

## 🙋 支持

如有问题，请查看日志或提交 Issue。

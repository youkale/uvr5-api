# 依赖管理说明

## 📦 依赖文件概述

本项目支持多种依赖管理方式，使用 `uv` 作为推荐的包管理器。

### 依赖文件列表

| 文件 | 用途 | 包管理器 |
|------|------|----------|
| `pyproject.toml` | 主要依赖配置（推荐）| uv / pip |
| `requirements.txt` | CPU 版本依赖 | pip / uv |
| `requirements-gpu.txt` | GPU 版本依赖（CUDA） | pip / uv |

## 🔧 核心依赖

### 必需依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| `flask` | >=3.0.0 | Web 框架 |
| `flask-httpauth` | >=4.8.0 | HTTP 认证 |
| `redis` | >=5.0.0 | **消息队列（优先级队列）** |
| `boto3` | >=1.34.0 | AWS S3 SDK |
| `requests` | >=2.31.0 | HTTP 客户端 |
| `audio-separator` | >=0.17.0 | UVR 音频分离库 |
| `python-dotenv` | >=1.0.0 | 环境变量管理 |
| `gunicorn` | >=21.2.0 | WSGI 服务器 |

### 音频处理依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| `onnxruntime` | >=1.16.0 | ONNX 运行时（CPU） |
| `onnxruntime-gpu` | >=1.16.0 | ONNX 运行时（GPU）* |
| `torch` | >=2.0.0 | PyTorch（GPU版本）* |
| `librosa` | >=0.10.1 | 音频分析库 |
| `soundfile` | >=0.12.1 | 音频文件读写 |
| `numpy` | >=1.24.0,<2.0.0 | 数值计算 |
| `tqdm` | >=4.66.0 | 进度条 |

**\* 仅在 `requirements-gpu.txt` 中**

## 📥 安装方法

### 方法 1：使用 uv（推荐）

uv 是 Rust 编写的超快 Python 包管理器。

#### 安装 uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 安装依赖

本项目是**应用程序项目**，不是 Python 包，因此推荐直接从 requirements 文件安装：

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
# CPU 版本
uv pip install -r requirements.txt

# GPU 版本（Linux CUDA）
uv pip install -r requirements-gpu.txt
```

**注意**：`pyproject.toml` 主要用于依赖版本管理和项目元数据。本项目不需要可编辑安装（`pip install -e .`）。

### 方法 2：使用 pip

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
# CPU 版本
pip install -r requirements.txt

# GPU 版本（Linux CUDA）
pip install -r requirements-gpu.txt
```

### 方法 3：使用 Docker

Docker 环境会自动安装所有依赖：

```bash
docker-compose up -d
```

## 🚀 快速开始

### 自动安装（推荐）

运行本地启动脚本会自动检测并安装依赖：

```bash
./start_local.sh
```

该脚本会：
1. ✅ 检测是否安装了 uv
2. ✅ 自动创建虚拟环境
3. ✅ 安装所有依赖
4. ✅ 启动所有服务

### 手动安装

```bash
# 1. 创建虚拟环境
uv venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖
uv pip install -r requirements.txt

# 4. 验证安装
python -c "import redis; print('Redis OK')"
python -c "import flask; print('Flask OK')"
python -c "import audio_separator; print('Audio Separator OK')"
```

## 🔄 迁移说明

### 从 Kafka 迁移到 Redis

项目已从 Kafka 迁移到 Redis，需要更新依赖：

**旧依赖（已移除）：**
```python
kafka-python>=2.0.2  # ❌ 已移除
```

**新依赖（已添加）：**
```python
redis>=5.0.0  # ✅ 已添加
```

### 更新步骤

如果你从旧版本升级：

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 卸载旧依赖
pip uninstall kafka-python -y

# 3. 重新安装所有依赖
uv pip install -r requirements.txt
```

## 🔍 依赖验证

### 检查已安装的包

```bash
# 使用 pip
pip list | grep -E "redis|flask|boto3|audio-separator"

# 使用 uv
uv pip list | grep -E "redis|flask|boto3|audio-separator"
```

### 验证关键组件

```bash
# 检查 Redis
python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping(); print('✅ Redis 连接成功')"

# 检查 Flask
python -c "import flask; print(f'✅ Flask {flask.__version__}')"

# 检查 audio-separator
python -c "from audio_separator.separator import Separator; print('✅ Audio Separator 可用')"

# 检查 boto3 (S3)
python -c "import boto3; print('✅ Boto3 可用')"
```

## 🎯 GPU 支持

### CPU 版本（默认）
使用 `requirements.txt` 或 `pyproject.toml`：
- `onnxruntime>=1.16.0` - CPU 推理

### GPU 版本（Linux CUDA）
使用 `requirements-gpu.txt`：
- `onnxruntime-gpu>=1.16.0` - GPU 推理
- `torch>=2.0.0` - PyTorch CUDA 支持

### 检查 GPU 支持

```bash
python check_gpu_support.py
```

输出示例：
```
GPU 支持检查
=====================================
系统: Linux
Python: 3.11.0
✓ CUDA Execution Provider detected
✓ GPU acceleration enabled
=====================================
```

## 📊 依赖大小对比

| 配置 | 安装大小 | 下载时间 |
|------|---------|---------|
| CPU 版本 | ~2GB | ~5分钟 |
| GPU 版本 | ~5GB | ~15分钟 |
| Docker 镜像 | ~3GB | ~10分钟 |

## 🔧 故障排除

### 问题：redis 安装失败

```bash
# 确保使用最新的 pip/uv
pip install --upgrade pip
# 或
uv self update

# 重新安装
uv pip install redis>=5.0.0
```

### 问题：audio-separator 依赖冲突

```bash
# 检查 numpy 版本（必须 <2.0）
pip show numpy

# 如果版本 >=2.0，降级
pip install "numpy>=1.24.0,<2.0.0"
```

### 问题：onnxruntime GPU 版本冲突

不能同时安装 `onnxruntime` 和 `onnxruntime-gpu`：

```bash
# 卸载 CPU 版本
pip uninstall onnxruntime -y

# 安装 GPU 版本
pip install onnxruntime-gpu>=1.16.0
```

## 📝 更新依赖

### 更新所有依赖到最新版本

```bash
# 使用 uv
uv pip install --upgrade -r requirements.txt

# 使用 pip
pip install --upgrade -r requirements.txt
```

### 冻结依赖版本

生成精确的依赖版本：

```bash
# 导出当前环境
pip freeze > requirements-freeze.txt

# 或使用 uv
uv pip freeze > requirements-freeze.txt
```

## 🌐 版本兼容性

| Python 版本 | 支持状态 | 说明 |
|------------|---------|------|
| 3.10 | ✅ 支持 | 最低要求 |
| 3.11 | ✅ 推荐 | 最佳性能 |
| 3.12 | ✅ 支持 | 最新版本 |
| 3.9 及以下 | ❌ 不支持 | 需要升级 |

## 📚 相关文档

- [uv 官方文档](https://github.com/astral-sh/uv)
- [Redis Python 文档](https://redis-py.readthedocs.io/)
- [audio-separator 文档](https://github.com/nomadkaraoke/python-audio-separator)
- [Flask 文档](https://flask.palletsprojects.com/)

## 🆕 版本历史

### v0.2.0 (当前)
- ✅ 迁移到 Redis 优先级队列
- ✅ 移除 Kafka 依赖
- ✅ 添加优先级支持
- ✅ 更新所有依赖文件

### v0.1.0 (旧版本)
- ❌ 使用 Kafka 消息队列
- ❌ 无优先级支持

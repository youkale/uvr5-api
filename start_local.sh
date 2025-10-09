#!/bin/bash

# UVR API 本地启动脚本（不使用 Docker）

set -e

echo "🎵 启动 UVR Audio Separation API 服务（本地模式）"
echo "=================================================="
echo ""

# 检查 Python 版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3，请先安装 Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python 版本: $PYTHON_VERSION"

# 检查是否安装了 uv
if command -v uv &> /dev/null; then
    echo "✓ 已安装 uv"
    USE_UV=true
else
    echo "⚠️  未安装 uv，将使用 pip"
    echo "   提示: 安装 uv 可以获得更快的速度: curl -LsSf https://astral.sh/uv/install.sh | sh"
    USE_UV=false
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  警告: 未找到 .env 文件"
    echo "   请复制并配置环境变量："
    echo "   cp env.example .env"
    echo "   然后编辑 .env 文件"
    echo ""
    read -p "是否使用默认配置继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 创建必要的目录
mkdir -p temp output logs

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo ""
    echo "📦 创建虚拟环境..."
    if [ "$USE_UV" = true ]; then
        uv venv
    else
        python3 -m venv .venv
    fi
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source .venv/bin/activate

# 安装依赖
if [ "$USE_UV" = true ]; then
    echo "📥 使用 uv 安装依赖..."
    uv pip install -r requirements-gpu.txt
else
    echo "📥 使用 pip 安装依赖..."
    pip install -r requirements-gpu.txt
fi

echo ""
echo "=================================================="
echo "✅ 环境准备完成！"
echo "=================================================="
echo ""

# 检查 Kafka 是否运行
echo "🔍 检查 Kafka 服务..."
KAFKA_HOST=$(grep KAFKA_BOOTSTRAP_SERVERS .env 2>/dev/null | cut -d'=' -f2 | cut -d':' -f1 || echo "localhost")
KAFKA_PORT=$(grep KAFKA_BOOTSTRAP_SERVERS .env 2>/dev/null | cut -d'=' -f2 | cut -d':' -f2 || echo "9092")

if ! nc -z "$KAFKA_HOST" "$KAFKA_PORT" 2>/dev/null; then
    echo "⚠️  警告: Kafka 服务未运行 ($KAFKA_HOST:$KAFKA_PORT)"
    echo ""
    echo "请先启动 Kafka："
    echo "  方案1 - 使用 Docker: docker-compose up -d zookeeper kafka"
    echo "  方案2 - 本地 Kafka: 启动本地 Kafka 服务"
    echo ""
    read -p "是否继续启动服务? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "🚀 启动服务..."
echo "=================================================="
echo ""

# 创建 PID 文件目录
mkdir -p .pids

# 启动 API 服务器
echo "1️⃣  启动 API 服务器 (端口 8000)..."
python app.py > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > .pids/api.pid
echo "   PID: $API_PID"
sleep 2

# 启动音频处理器
echo "2️⃣  启动音频处理器..."
python processor.py > logs/processor.log 2>&1 &
PROCESSOR_PID=$!
echo $PROCESSOR_PID > .pids/processor.pid
echo "   PID: $PROCESSOR_PID"
sleep 2

# 启动 S3 上传器
echo "3️⃣  启动 S3 上传器..."
python uploader.py > logs/uploader.log 2>&1 &
UPLOADER_PID=$!
echo $UPLOADER_PID > .pids/uploader.pid
echo "   PID: $UPLOADER_PID"
sleep 2

echo ""
echo "=================================================="
echo "✅ 所有服务已启动！"
echo "=================================================="
echo ""

# 检查进程是否运行
sleep 2
if ps -p $API_PID > /dev/null; then
    echo "✓ API 服务器运行中 (PID: $API_PID)"
else
    echo "❌ API 服务器启动失败，查看日志: logs/api.log"
fi

if ps -p $PROCESSOR_PID > /dev/null; then
    echo "✓ 音频处理器运行中 (PID: $PROCESSOR_PID)"
else
    echo "❌ 音频处理器启动失败，查看日志: logs/processor.log"
fi

if ps -p $UPLOADER_PID > /dev/null; then
    echo "✓ S3 上传器运行中 (PID: $UPLOADER_PID)"
else
    echo "❌ S3 上传器启动失败，查看日志: logs/uploader.log"
fi

echo ""
echo "=================================================="
echo "📋 服务信息"
echo "=================================================="
echo ""
echo "  API 地址:     http://localhost:8000"
echo "  健康检查:     curl http://localhost:8000/health"
echo "  认证测试:     curl -u admin:password http://localhost:8000/health"
echo ""
echo "📖 查看日志："
echo "  API:          tail -f logs/api.log"
echo "  处理器:       tail -f logs/processor.log"
echo "  上传器:       tail -f logs/uploader.log"
echo "  所有日志:     tail -f logs/*.log"
echo ""
echo "🛑 停止服务："
echo "  ./stop_local.sh"
echo ""
echo "=================================================="

# 等待用户操作
echo ""
read -p "按 Enter 查看实时日志（Ctrl+C 退出日志查看，服务继续运行）..."
tail -f logs/*.log

#!/bin/bash

# 测试 Kafka Consumer 优雅关闭

echo "🧪 测试 Kafka Consumer 优雅关闭"
echo "================================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. 确保服务正在运行
echo "📋 步骤 1: 检查服务状态"
echo "----------------------------------------"

if [ ! -f ".pids/processor.pid" ] || [ ! -f ".pids/uploader.pid" ]; then
    echo -e "${YELLOW}⚠️  服务未运行，正在启动...${NC}"
    ./start_local.sh
    sleep 5
else
    echo -e "${GREEN}✓ 服务正在运行${NC}"
fi

echo ""

# 2. 获取 PID
PROCESSOR_PID=$(cat .pids/processor.pid 2>/dev/null)
UPLOADER_PID=$(cat .pids/uploader.pid 2>/dev/null)

echo "📋 步骤 2: 获取进程 PID"
echo "----------------------------------------"
echo "Processor PID: $PROCESSOR_PID"
echo "Uploader PID: $UPLOADER_PID"
echo ""

# 3. 测试 SIGTERM 信号
echo "📋 步骤 3: 测试 SIGTERM 信号"
echo "----------------------------------------"

# 备份日志文件
cp logs/processor.log logs/processor.log.backup 2>/dev/null
cp logs/uploader.log logs/uploader.log.backup 2>/dev/null

echo "发送 SIGTERM 到 Processor (PID: $PROCESSOR_PID)..."
kill -TERM $PROCESSOR_PID

echo "等待 2 秒..."
sleep 2

# 检查是否优雅关闭
echo ""
echo "检查 Processor 关闭日志:"
echo "----------------------------------------"

if grep -q "Received SIGTERM" logs/processor.log; then
    echo -e "${GREEN}✓ 收到 SIGTERM 信号${NC}"
else
    echo -e "${RED}✗ 未收到 SIGTERM 信号${NC}"
fi

if grep -q "initiating graceful shutdown" logs/processor.log; then
    echo -e "${GREEN}✓ 开始优雅关闭${NC}"
else
    echo -e "${RED}✗ 未开始优雅关闭${NC}"
fi

if grep -q "Shutdown flag set" logs/processor.log; then
    echo -e "${GREEN}✓ 停止消费新消息${NC}"
else
    echo -e "${RED}✗ 未停止消费${NC}"
fi

if grep -q "Closing Kafka consumer" logs/processor.log; then
    echo -e "${GREEN}✓ 关闭 Kafka consumer${NC}"
else
    echo -e "${RED}✗ 未关闭 consumer${NC}"
fi

if grep -q "Kafka producer closed" logs/processor.log; then
    echo -e "${GREEN}✓ 关闭 Kafka producer${NC}"
else
    echo -e "${RED}✗ 未关闭 producer${NC}"
fi

if grep -q "Processor shutdown complete" logs/processor.log; then
    echo -e "${GREEN}✓ 完成关闭${NC}"
else
    echo -e "${RED}✗ 未完成关闭${NC}"
fi

echo ""
echo "检查 Uploader 关闭日志:"
echo "----------------------------------------"

echo "发送 SIGTERM 到 Uploader (PID: $UPLOADER_PID)..."
kill -TERM $UPLOADER_PID

echo "等待 2 秒..."
sleep 2

if grep -q "Received SIGTERM" logs/uploader.log; then
    echo -e "${GREEN}✓ 收到 SIGTERM 信号${NC}"
else
    echo -e "${RED}✗ 未收到 SIGTERM 信号${NC}"
fi

if grep -q "initiating graceful shutdown" logs/uploader.log; then
    echo -e "${GREEN}✓ 开始优雅关闭${NC}"
else
    echo -e "${RED}✗ 未开始优雅关闭${NC}"
fi

if grep -q "Shutdown flag set" logs/uploader.log; then
    echo -e "${GREEN}✓ 停止消费新消息${NC}"
else
    echo -e "${RED}✗ 未停止消费${NC}"
fi

if grep -q "Closing Kafka consumer" logs/uploader.log; then
    echo -e "${GREEN}✓ 关闭 Kafka consumer${NC}"
else
    echo -e "${RED}✗ 未关闭 consumer${NC}"
fi

if grep -q "Uploader shutdown complete" logs/uploader.log; then
    echo -e "${GREEN}✓ 完成关闭${NC}"
else
    echo -e "${RED}✗ 未完成关闭${NC}"
fi

echo ""

# 4. 检查进程是否真正退出
echo "📋 步骤 4: 验证进程已退出"
echo "----------------------------------------"

if ps -p $PROCESSOR_PID > /dev/null 2>&1; then
    echo -e "${RED}✗ Processor 进程仍在运行 (PID: $PROCESSOR_PID)${NC}"
    echo "  尝试强制终止..."
    kill -9 $PROCESSOR_PID
else
    echo -e "${GREEN}✓ Processor 进程已正确退出${NC}"
fi

if ps -p $UPLOADER_PID > /dev/null 2>&1; then
    echo -e "${RED}✗ Uploader 进程仍在运行 (PID: $UPLOADER_PID)${NC}"
    echo "  尝试强制终止..."
    kill -9 $UPLOADER_PID
else
    echo -e "${GREEN}✓ Uploader 进程已正确退出${NC}"
fi

echo ""

# 5. 测试 stop_local.sh 脚本
echo "📋 步骤 5: 测试 stop_local.sh 脚本"
echo "----------------------------------------"

# 重新启动服务
echo "重新启动服务..."
./start_local.sh
sleep 3

# 清理日志
> logs/processor.log
> logs/uploader.log

# 使用 stop_local.sh 停止
echo "使用 stop_local.sh 停止服务..."
./stop_local.sh

sleep 2

echo ""
echo "检查停止脚本效果:"
echo "----------------------------------------"

# 检查日志
if grep -q "Received SIGTERM" logs/processor.log; then
    echo -e "${GREEN}✓ Processor 收到 SIGTERM${NC}"
else
    echo -e "${YELLOW}⚠️  Processor 可能被强制终止 (SIGKILL)${NC}"
fi

if grep -q "Received SIGTERM" logs/uploader.log; then
    echo -e "${GREEN}✓ Uploader 收到 SIGTERM${NC}"
else
    echo -e "${YELLOW}⚠️  Uploader 可能被强制终止 (SIGKILL)${NC}"
fi

echo ""

# 6. 总结
echo "================================================"
echo "📊 测试总结"
echo "================================================"
echo ""

PROCESSOR_GRACEFUL=0
UPLOADER_GRACEFUL=0

# 恢复备份日志用于检查
if [ -f "logs/processor.log.backup" ]; then
    if grep -q "Processor shutdown complete" logs/processor.log.backup; then
        PROCESSOR_GRACEFUL=1
    fi
fi

if [ -f "logs/uploader.log.backup" ]; then
    if grep -q "Uploader shutdown complete" logs/uploader.log.backup; then
        UPLOADER_GRACEFUL=1
    fi
fi

if [ $PROCESSOR_GRACEFUL -eq 1 ] && [ $UPLOADER_GRACEFUL -eq 1 ]; then
    echo -e "${GREEN}✅ 所有服务都支持优雅关闭${NC}"
    echo ""
    echo "优雅关闭流程:"
    echo "  1. 收到 SIGTERM/SIGINT 信号"
    echo "  2. 设置关闭标志"
    echo "  3. 停止接收新消息"
    echo "  4. 关闭 Kafka consumer"
    echo "  5. Flush 并关闭 producer"
    echo "  6. 进程正常退出"
else
    echo -e "${YELLOW}⚠️  部分服务可能不支持完整的优雅关闭${NC}"
    echo ""
    if [ $PROCESSOR_GRACEFUL -eq 0 ]; then
        echo "  - Processor: 需要检查"
    fi
    if [ $UPLOADER_GRACEFUL -eq 0 ]; then
        echo "  - Uploader: 需要检查"
    fi
fi

echo ""
echo "💡 提示:"
echo "  - 查看完整日志: tail -f logs/processor.log logs/uploader.log"
echo "  - 手动测试: kill -TERM <PID>"
echo "  - 强制终止: kill -9 <PID>"
echo ""

# 清理备份文件
rm -f logs/*.backup

echo "================================================"

#!/bin/bash

# Redis 队列状态检查脚本

echo "🔍 Redis 队列状态检查"
echo "======================================"
echo ""

# 检查是否在 Docker 环境中
if docker ps | grep -q uvr-redis; then
    REDIS_CMD="docker exec -it uvr-redis redis-cli"
    echo "✓ 检测到 Docker 环境"
else
    REDIS_CMD="redis-cli"
    echo "✓ 使用本地 Redis"
fi

echo ""
echo "📊 队列统计:"
echo "--------------------------------------"

# 任务队列大小
TASK_QUEUE_SIZE=$($REDIS_CMD ZCARD uvr_tasks 2>/dev/null || echo "0")
echo "  任务队列 (uvr_tasks):      $TASK_QUEUE_SIZE"

# 结果队列大小
RESULT_QUEUE_SIZE=$($REDIS_CMD ZCARD uvr_results 2>/dev/null || echo "0")
echo "  结果队列 (uvr_results):    $RESULT_QUEUE_SIZE"

echo ""
echo "📋 任务队列前5个任务:"
echo "--------------------------------------"
$REDIS_CMD ZRANGE uvr_tasks 0 4 WITHSCORES 2>/dev/null | while read -r line; do
    echo "  $line"
done

echo ""
echo "📋 结果队列前5个任务:"
echo "--------------------------------------"
$REDIS_CMD ZRANGE uvr_results 0 4 WITHSCORES 2>/dev/null | while read -r line; do
    echo "  $line"
done

echo ""
echo "======================================"
echo ""
echo "💡 有用的 Redis 命令:"
echo "  查看任务队列大小:    $REDIS_CMD ZCARD uvr_tasks"
echo "  查看结果队列大小:    $REDIS_CMD ZCARD uvr_results"
echo "  清空任务队列:        $REDIS_CMD DEL uvr_tasks"
echo "  清空结果队列:        $REDIS_CMD DEL uvr_results"
echo "  查看所有键:          $REDIS_CMD KEYS '*'"
echo ""

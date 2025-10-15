# 从 Kafka 迁移到 Redis 优先级队列

## 📋 迁移概述

本项目已从 Apache Kafka 迁移到 Redis 优先级队列系统。

### 主要变更

| 组件 | 旧版本 (Kafka) | 新版本 (Redis) |
|------|---------------|---------------|
| 消息队列 | Kafka + Zookeeper | Redis (ZSet) |
| 优先级支持 | ❌ | ✅ (1-5级) |
| 部署复杂度 | 高 (2个服务) | 低 (1个服务) |
| 内存占用 | 高 (~500MB+) | 低 (~50MB) |
| 启动时间 | 慢 (~30s) | 快 (~2s) |

## 🔄 迁移步骤

### 1. Docker 环境迁移

如果你使用 Docker Compose：

```bash
# 1. 停止旧服务
docker-compose down

# 2. 清理旧数据（可选）
docker-compose down -v

# 3. 拉取最新代码
git pull

# 4. 重新启动服务
./start.sh
```

服务将自动使用 Redis 而不是 Kafka。

### 2. 本地环境迁移

如果你在本地运行：

```bash
# 1. 停止旧服务
./stop_local.sh

# 2. 安装 Redis
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 --name redis redis:latest

# 3. 更新 Python 依赖
pip install -r requirements.txt

# 4. 更新环境变量（见下文）

# 5. 重新启动服务
./start_local.sh
```

### 3. 环境变量更新

#### 移除以下 Kafka 配置：
```bash
# ❌ 删除这些
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TASK_TOPIC=uvr_tasks
KAFKA_RESULT_TOPIC=uvr_results
KAFKA_PROCESSOR_GROUP_ID=uvr_processor_group
KAFKA_UPLOADER_GROUP_ID=uvr_uploader_group
```

#### 添加 Redis 配置：
```bash
# ✅ 添加这些
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_TASK_QUEUE=uvr_tasks
REDIS_RESULT_QUEUE=uvr_results
DEFAULT_PRIORITY=3
```

### 4. 验证迁移

```bash
# 检查 Redis 连接
redis-cli ping
# 应返回: PONG

# 检查 API 健康状态
curl http://localhost:8000/health
# 应返回包含 Redis 状态的 JSON

# 查看队列状态
./check_redis_queue.sh
```

## 🆕 新功能：任务优先级

### API 请求示例

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

### 优先级说明

- **5** - 最高优先级（紧急任务）
- **4** - 高优先级
- **3** - 中等优先级（默认）
- **2** - 低优先级
- **1** - 最低优先级

### 优先级算法

```
score = timestamp * (6 - priority)
```

分数越低，任务越早被处理：
- 优先级 5 → score = timestamp × 1 → 最先处理
- 优先级 3 → score = timestamp × 3 → 中间处理
- 优先级 1 → score = timestamp × 5 → 最后处理

## 📊 监控队列

### 使用检查脚本

```bash
./check_redis_queue.sh
```

### 使用 Redis CLI

```bash
# Docker 环境
docker exec -it uvr-redis redis-cli

# 本地环境
redis-cli

# 查看队列大小
ZCARD uvr_tasks
ZCARD uvr_results

# 查看队列内容
ZRANGE uvr_tasks 0 -1 WITHSCORES
ZRANGE uvr_results 0 -1 WITHSCORES

# 查看最高优先级任务（分数最低）
ZRANGE uvr_tasks 0 0 WITHSCORES

# 清空队列（谨慎使用）
DEL uvr_tasks
DEL uvr_results
```

## 🔧 启动脚本变更

### Docker 模式（`start.sh`）

- **之前**: 启动 Zookeeper + Kafka + API + Processor + Uploader
- **现在**: 启动 Redis + API + Processor + Uploader

### 本地模式（`start_local.sh`）

- **之前**: 检查 Kafka 连接
- **现在**: 检查 Redis 连接

## 📁 文件变更清单

### 新增文件
- `redis_queue.py` - Redis 优先级队列抽象层
- `check_redis_queue.sh` - Redis 队列状态检查脚本
- `MIGRATION.md` - 本迁移文档

### 修改文件
- `config.py` - Kafka 配置 → Redis 配置
- `app.py` - 集成 Redis 队列，添加 priority 参数
- `processor.py` - 使用 Redis 队列
- `uploader.py` - 使用 Redis 队列，增强错误处理
- `requirements.txt` - `kafka-python` → `redis`
- `docker-compose.yml` - Kafka/Zookeeper → Redis
- `start.sh` - 更新服务提示
- `start_local.sh` - 检查 Redis 而非 Kafka
- `README.md` - 更新文档

### 删除依赖
- `kafka-python>=2.0.2` ❌
- 添加 `redis>=5.0.0` ✅

## 🐛 故障排除

### Redis 连接失败

```bash
# 检查 Redis 是否运行
redis-cli ping

# 检查端口
netstat -an | grep 6379

# 查看 Redis 日志
tail -f /var/log/redis/redis-server.log
```

### 队列积压

```bash
# 查看队列大小
./check_redis_queue.sh

# 如果队列积压，检查 processor/uploader 是否运行
docker-compose logs -f processor
docker-compose logs -f uploader
```

### 清空积压队列

```bash
# ⚠️ 谨慎：这会删除所有待处理任务
redis-cli DEL uvr_tasks uvr_results
```

## 📈 性能对比

### 启动时间
- Kafka: ~30秒 (Zookeeper + Kafka 初始化)
- Redis: ~2秒 (Redis 快速启动)

### 内存占用
- Kafka: ~500MB (Zookeeper 200MB + Kafka 300MB)
- Redis: ~50MB (轻量级)

### 延迟
- Kafka: ~10-50ms
- Redis: ~1-5ms (更低延迟)

### 吞吐量
- Kafka: 10,000+ msg/s
- Redis: 50,000+ ops/s (单线程)

**结论**: 对于我们的使用场景（音频处理任务），Redis 的性能和简单性更合适。

## 🎯 后续优化建议

1. **Redis 持久化**: 已启用 AOF (appendonly yes)
2. **Redis 集群**: 如需高可用，考虑 Redis Sentinel 或 Cluster
3. **监控**: 考虑添加 Redis 监控（Redis Exporter + Grafana）
4. **备份**: 定期备份 Redis RDB/AOF 文件
5. **限流**: 添加 API 限流保护

## 📞 支持

如有问题，请查看：
1. 日志文件：`logs/*.log` (本地) 或 `docker-compose logs -f` (Docker)
2. Redis 状态：`./check_redis_queue.sh`
3. API 健康检查：`curl http://localhost:8000/health`

## ✅ 迁移完成检查清单

- [ ] Redis 服务运行正常
- [ ] 环境变量已更新
- [ ] Python 依赖已更新
- [ ] API 健康检查通过
- [ ] 能够成功提交任务
- [ ] Processor 能够处理任务
- [ ] Uploader 能够上传结果
- [ ] Webhook 回调正常
- [ ] 优先级功能正常工作

完成所有检查项后，迁移即完成！🎉

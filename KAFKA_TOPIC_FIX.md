# Kafka Topic 问题修复

## 问题诊断

### 症状
从日志中看到：
```
kafka.coordinator - INFO - Successfully joined group uvr_processor_group
kafka.consumer.subscription_state - INFO - Updated partition assignment: []  ← 空的分区分配
kafka.coordinator.consumer - INFO - Setting newly assigned partitions set() for group uvr_processor_group
```

**问题**：Consumer 成功加入了 consumer group，但是没有被分配到任何分区。

### 根本原因

**Topics 不存在**：
- `uvr_tasks` - 不存在 ❌
- `uvr_results` - 不存在 ❌

当 Kafka Consumer 尝试订阅一个不存在的 topic 时：
1. Consumer 可以成功连接到 Kafka
2. Consumer 可以加入 consumer group
3. 但是不会被分配到任何分区（因为 topic 不存在）
4. 导致无法消费任何消息

## 解决方案

### 1. ✅ 已创建 Topics

使用以下命令创建了必需的 topics：

```python
from kafka.admin import KafkaAdminClient, NewTopic

topics_to_create = [
    NewTopic(name='uvr_tasks', num_partitions=1, replication_factor=1),
    NewTopic(name='uvr_results', num_partitions=1, replication_factor=1)
]
admin.create_topics(new_topics=topics_to_create)
```

### 2. 验证 Topics

```bash
# 使用诊断脚本验证
python3 check_kafka_consumer.py
```

**预期输出**：
```
2️⃣ 现有 Topics:
  ✓ uvr_tasks
  ✓ uvr_results

3️⃣ 检查必需的 Topics:
  ✓ uvr_tasks - 存在
    分区数: 1
  ✓ uvr_results - 存在
    分区数: 1

5️⃣ 测试 Consumer 连接...

Processor Consumer (uvr_processor_group):
  ✓ 已分配分区: {TopicPartition(topic='uvr_tasks', partition=0)}

Uploader Consumer (uvr_uploader_group):
  ✓ 已分配分区: {TopicPartition(topic='uvr_results', partition=0)}
```

### 3. 重启服务

```bash
# 停止当前服务
./stop_local.sh

# 启动服务
./start_local.sh

# 查看日志确认分区分配
tail -f logs/processor.log | grep partition
tail -f logs/uploader.log | grep partition
```

**预期日志**：
```
kafka.consumer.subscription_state - INFO - Updated partition assignment: [TopicPartition(topic='uvr_tasks', partition=0)]
kafka.coordinator.consumer - INFO - Setting newly assigned partitions {TopicPartition(topic='uvr_tasks', partition=0)} for group uvr_processor_group
```

## 配置检查

### ✅ Consumer 配置正确

**processor.py**:
```python
self.consumer = KafkaConsumer(
    config.KAFKA_TASK_TOPIC,  # 'uvr_tasks'
    group_id=config.KAFKA_PROCESSOR_GROUP_ID,  # 'uvr_processor_group'
    ...
)
```

**uploader.py**:
```python
self.consumer = KafkaConsumer(
    config.KAFKA_RESULT_TOPIC,  # 'uvr_results'
    group_id=config.KAFKA_UPLOADER_GROUP_ID,  # 'uvr_uploader_group'
    ...
)
```

### ✅ Group ID 独立

- Processor: `uvr_processor_group`
- Uploader: `uvr_uploader_group`

两个 consumer 使用不同的 group ID，可以独立消费各自的 topic。

## 为什么会出现这个问题？

### Kafka Topic 创建方式

Kafka 有两种创建 topic 的方式：

1. **自动创建** (auto.create.topics.enable=true)
   - Producer 首次写入不存在的 topic 时自动创建
   - Consumer 首次订阅不存在的 topic 时自动创建

2. **手动创建** (推荐)
   - 使用 Admin API 或命令行工具显式创建
   - 可以精确控制分区数和副本数

**本项目的情况**：
- Kafka 服务器可能禁用了自动创建 topic
- 或者 Consumer 启动时 topic 还未创建
- 导致 Consumer 无法订阅

## 预防措施

### 1. 在服务启动前确保 Topics 存在

可以在 `start_local.sh` 中添加：

```bash
# 确保 Kafka topics 存在
echo "Checking Kafka topics..."
python3 check_kafka_consumer.py > /dev/null 2>&1 || echo "Warning: Kafka topics check failed"
```

### 2. 使用 Docker Compose Init

在 `docker-compose.yml` 中添加初始化脚本：

```yaml
services:
  kafka-init:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - kafka
    entrypoint: [ '/bin/sh', '-c' ]
    command: |
      "
      # Wait for Kafka to be ready
      cub kafka-ready -b kafka:9092 1 20

      # Create topics
      kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic uvr_tasks --partitions 1 --replication-factor 1
      kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic uvr_results --partitions 1 --replication-factor 1

      echo 'Kafka topics created successfully'
      "
```

### 3. 应用程序启动时检查

在 `processor.py` 和 `uploader.py` 的 `__init__` 方法中添加：

```python
def _ensure_topic_exists(self):
    """Ensure Kafka topic exists before subscribing"""
    from kafka.admin import KafkaAdminClient, NewTopic

    try:
        admin = KafkaAdminClient(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(',')
        )

        existing_topics = admin.list_topics()

        if config.KAFKA_TASK_TOPIC not in existing_topics:
            logger.warning(f"Topic {config.KAFKA_TASK_TOPIC} does not exist, creating...")
            topic = NewTopic(
                name=config.KAFKA_TASK_TOPIC,
                num_partitions=1,
                replication_factor=1
            )
            admin.create_topics([topic])
            logger.info(f"Topic {config.KAFKA_TASK_TOPIC} created")

        admin.close()
    except Exception as e:
        logger.warning(f"Failed to check/create topic: {e}")
```

## 常见问题排查

### Q1: Consumer 加入 group 但没有分配分区

**检查**:
```bash
python3 check_kafka_consumer.py
```

**原因**:
- Topic 不存在
- Topic 没有分区
- Topic 名称配置错误

### Q2: 日志显示 "MemberIdRequiredError"

**日志**:
```
Failed to join group: [Error 79] MemberIdRequiredError
```

**这是正常的**：
- 这是 Kafka 的正常握手过程
- Consumer 第一次加入 group 时需要先获取 member_id
- 然后重试加入，这是预期行为

### Q3: 分区重新分配 (Rebalance)

**日志**:
```
(Re-)joining group uvr_processor_group
```

**常见原因**:
- 新 consumer 加入
- Consumer 崩溃或退出
- Consumer 处理超时（超过 max_poll_interval_ms）

## 验证清单

- [x] Kafka 服务运行正常
- [x] Topics 已创建 (`uvr_tasks`, `uvr_results`)
- [x] Topics 有分区 (至少 1 个分区)
- [x] Group ID 配置正确
- [x] Bootstrap servers 配置正确
- [ ] 重启服务后分区正常分配
- [ ] 发送测试消息可以被消费

## 总结

**问题**：Topics 不存在导致 Consumer 无法分配分区

**解决**：
1. ✅ 创建了 `uvr_tasks` 和 `uvr_results` topics
2. ✅ 每个 topic 配置了 1 个分区
3. ✅ 提供了诊断工具 `check_kafka_consumer.py`

**下一步**：
1. 重启服务
2. 验证分区分配
3. 发送测试请求验证功能

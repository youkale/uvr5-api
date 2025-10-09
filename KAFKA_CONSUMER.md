# Kafka 消费者配置说明

## 核心配置

### 1. 每次只读取一条消息

```python
max_poll_records=1  # 每次 poll 只获取1条消息
```

**作用**：
- 确保消费者每次只处理一条消息
- 避免批量拉取导致的并发处理问题
- 简化错误处理和重试逻辑

**默认值**: 500（会一次性拉取多条消息）

### 2. 手动提交 Offset

```python
enable_auto_commit=False  # 禁用自动提交
```

**作用**：
- 完全控制何时提交 offset
- 只有在消息处理成功后才提交
- 避免消息丢失

**提交时机**：
```python
# 处理成功后立即提交
self._process_task(task_data)
self.consumer.commit()  # 手动提交
```

## 完整配置解析

### Processor (音频处理消费者)

```python
self.consumer = KafkaConsumer(
    config.KAFKA_TASK_TOPIC,              # Topic: uvr_tasks
    bootstrap_servers='localhost:9092',    # Kafka 服务器
    group_id='uvr_processor_group',        # 消费者组 ID

    # 序列化配置
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    key_deserializer=lambda k: k.decode('utf-8') if k else None,

    # Offset 配置
    auto_offset_reset='latest',            # 从最新消息开始
    enable_auto_commit=False,              # 禁用自动提交

    # 消息拉取配置
    max_poll_records=1,                    # 每次只读取1条
    max_poll_interval_ms=600000,           # 10分钟最大处理时间

    # 会话配置
    session_timeout_ms=60000,              # 60秒会话超时
    heartbeat_interval_ms=10000            # 10秒心跳间隔
)
```

### Uploader (S3上传消费者)

```python
self.consumer = KafkaConsumer(
    config.KAFKA_RESULT_TOPIC,             # Topic: uvr_results
    bootstrap_servers='localhost:9092',    # Kafka 服务器
    group_id='uvr_uploader_group',         # 消费者组 ID（独立）

    # 序列化配置
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    key_deserializer=lambda k: k.decode('utf-8') if k else None,

    # Offset 配置
    auto_offset_reset='latest',            # 从最新消息开始
    enable_auto_commit=False,              # 禁用自动提交

    # 消息拉取配置
    max_poll_records=1,                    # 每次只读取1条
    max_poll_interval_ms=300000,           # 5分钟最大处理时间

    # 会话配置
    session_timeout_ms=60000,              # 60秒会话超时
    heartbeat_interval_ms=10000            # 10秒心跳间隔
)
```

## 消息处理流程

### 标准处理流程

```python
def start(self):
    for message in self.consumer:
        try:
            # 1. 获取消息
            task_data = message.value
            task_uuid = task_data.get('task_uuid')

            # 2. 处理消息
            self._process_task(task_data)

            # 3. 处理成功后立即手动提交
            self.consumer.commit()
            logger.info(f"[{task_uuid}] Offset committed successfully")

        except Exception as e:
            logger.error(f"Error: {str(e)}")

            # 4. 即使失败也提交，避免重复处理
            try:
                self.consumer.commit()
                logger.warning("Offset committed despite error")
            except Exception as commit_error:
                logger.error(f"Failed to commit: {commit_error}")
            continue
```

### 处理流程说明

1. **消息获取**: `for message in self.consumer` 每次只获取1条消息（`max_poll_records=1`）
2. **消息处理**: 执行实际的业务逻辑（下载、分离、上传等）
3. **成功提交**: 处理完成后调用 `commit()` 提交 offset
4. **失败处理**: 即使处理失败也提交 offset，避免无限重试

## 为什么每次只读取一条消息？

### 优点

✅ **简化错误处理**
- 每条消息独立处理和提交
- 失败不影响其他消息

✅ **避免超时**
- 单条消息处理时间可预测
- 不会因批量处理导致 `max_poll_interval_ms` 超时

✅ **资源控制**
- 单进程只处理一个任务
- 避免内存溢出（音频文件可能很大）

✅ **提交精确**
- 每条消息处理完立即提交
- 不会出现部分提交的问题

✅ **易于监控**
- 清晰的日志：一条消息一个周期
- 容易追踪每个任务的状态

### 缺点（已通过架构设计缓解）

❌ **吞吐量较低**
- 解决方案：启动多个 processor 实例并行处理
- Kafka 会自动在消费者间分配消息

❌ **网络开销**
- 影响很小：Kafka 客户端有内部缓冲
- 实际网络调用次数不会显著增加

## 手动提交策略

### 当前策略：Always Commit（总是提交）

```python
try:
    self._process_task(task_data)
    self.consumer.commit()  # 成功时提交
except Exception as e:
    self.consumer.commit()  # 失败时也提交
```

**优点**：
- 不会重复处理相同消息
- 避免陷入无限重试循环
- 适合幂等性难以保证的场景

**适用场景**：
- 外部依赖较多（下载、S3上传）
- 失败通常不可恢复（如源文件不存在）
- 已有失败回调机制

### 替代策略：Retry on Failure（失败重试）

如果需要失败重试，可以修改为：

```python
try:
    self._process_task(task_data)
    self.consumer.commit()  # 只在成功时提交
except Exception as e:
    # 不提交，消息会被重新消费
    logger.error(f"Will retry: {str(e)}")
    # 可以实现重试次数限制
```

**需要配合**：
1. 在消息中添加重试计数器
2. 设置最大重试次数（如3次）
3. 超过次数后提交并发送失败回调

## 超时配置说明

### max_poll_interval_ms

**Processor**: 600000ms (10分钟)
```python
max_poll_interval_ms=600000
```

**原因**：
- 下载大音频文件可能需要时间
- 音频分离处理可能需要3-5分钟
- 包含一定安全余量

**Uploader**: 300000ms (5分钟)
```python
max_poll_interval_ms=300000
```

**原因**：
- S3 上传通常比处理快
- 2个文件上传 + 回调通知
- 足够的余量

### session_timeout_ms & heartbeat_interval_ms

```python
session_timeout_ms=60000      # 60秒
heartbeat_interval_ms=10000    # 10秒
```

**作用**：
- 心跳每10秒发送一次
- 60秒内无心跳则认为消费者死亡
- 触发 rebalance，消息分配给其他消费者

**建议比例**：
```
heartbeat_interval_ms < session_timeout_ms / 3
```

## 监控和调试

### 查看消费进度

```bash
# 查看消息接收
grep "Received task" logs/processor.log | tail -n 20
grep "Received result" logs/uploader.log | tail -n 20
```

### 查看提交状态

```bash
# 查看成功提交
grep "Offset committed successfully" logs/processor.log | tail -n 20

# 查看失败提交
grep "Offset committed despite error" logs/processor.log | tail -n 20
```

### 查看处理时间

```bash
# 从接收到提交的时间跨度
grep -A 100 "Received task" logs/processor.log | grep "Offset committed"
```

### Kafka 工具查看 Consumer Group

```bash
# 进入 Kafka 容器（Docker）
docker-compose exec kafka bash

# 查看消费者组状态
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group uvr_processor_group --describe

kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group uvr_uploader_group --describe
```

输出示例：
```
GROUP                TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
uvr_processor_group  uvr_tasks       0          150             150             0
```

- **CURRENT-OFFSET**: 已提交的 offset
- **LOG-END-OFFSET**: 最新消息的 offset
- **LAG**: 积压的消息数（0表示无积压）

## 性能优化建议

### 水平扩展

如果单个 processor 处理速度不够：

```bash
# 启动多个 processor 实例
python3 processor.py &  # 实例1
python3 processor.py &  # 实例2
python3 processor.py &  # 实例3
```

Kafka 会自动分配消息给不同实例。

### 增加分区数

```bash
# 进入 Kafka 容器
docker-compose exec kafka bash

# 增加 topic 分区数（如增加到3个）
kafka-topics.sh --bootstrap-server localhost:9092 \
  --topic uvr_tasks --alter --partitions 3
```

**注意**：
- 分区数 ≥ 消费者数才能充分利用并行
- 分区数只能增加，不能减少

## 故障场景处理

### 场景1：Processor 处理时崩溃

**结果**：
- 因为 `enable_auto_commit=False`，offset 未提交
- 重启后，消息会被重新消费
- 可能导致重复处理

**解决**：
- 在任务开始时记录状态（如写数据库）
- 处理前检查是否已处理过（幂等性）

### 场景2：网络抖动导致心跳超时

**结果**：
- Consumer 被踢出 group
- 触发 rebalance
- 重新加入后继续消费

**解决**：
- 已配置合理的 `session_timeout_ms`
- 日志会显示 rebalance 信息

### 场景3：消息堆积

**结果**：
- LAG 持续增加
- 处理速度 < 生产速度

**解决**：
1. 增加 processor 实例数
2. 增加 topic 分区数
3. 优化处理逻辑（如下载优化）

## 配置建议总结

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `max_poll_records` | **1** | 每次只读取1条，简化处理 |
| `enable_auto_commit` | **False** | 手动提交，确保可靠性 |
| `max_poll_interval_ms` | **600000** (processor)<br>**300000** (uploader) | 根据处理时间设置 |
| `session_timeout_ms` | **60000** | 1分钟会话超时 |
| `heartbeat_interval_ms` | **10000** | 10秒心跳 |
| `auto_offset_reset` | **latest** | 从最新消息开始 |

## 总结

✅ **已配置**：
- `max_poll_records=1` - 每次只读取1条消息
- `enable_auto_commit=False` - 手动提交 offset
- 处理完成后立即调用 `commit()`
- 即使失败也提交，避免重复处理

✅ **符合需求**：
- ✓ 每次读取一条
- ✓ 处理完成后手动提交
- ✓ 简单可靠的错误处理
- ✓ 易于水平扩展

✅ **监控就绪**：
- 详细的日志记录
- 清晰的提交状态
- 易于追踪问题

#!/usr/bin/env python3
"""
检查 Kafka Consumer 配置和连接状态
"""
import sys
sys.path.insert(0, '/Users/sean/dev_projects/uvr_api')

import config
from kafka import KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
import time

print("🔍 Kafka Consumer 配置检查")
print("=" * 60)

print("\n📋 配置信息:")
print(f"  Bootstrap Servers: {config.KAFKA_BOOTSTRAP_SERVERS}")
print(f"  Task Topic: {config.KAFKA_TASK_TOPIC}")
print(f"  Result Topic: {config.KAFKA_RESULT_TOPIC}")
print(f"  Processor Group ID: {config.KAFKA_PROCESSOR_GROUP_ID}")
print(f"  Uploader Group ID: {config.KAFKA_UPLOADER_GROUP_ID}")

print("\n" + "=" * 60)
print("\n1️⃣ 检查 Kafka 连接...")
try:
    admin_client = KafkaAdminClient(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','),
        client_id='config-checker'
    )
    print("✓ Kafka 连接成功")

    # 列出所有 topics
    print("\n2️⃣ 现有 Topics:")
    topics = admin_client.list_topics()
    for topic in sorted(topics):
        print(f"  • {topic}")

    # 检查我们需要的 topics
    print("\n3️⃣ 检查必需的 Topics:")
    required_topics = [config.KAFKA_TASK_TOPIC, config.KAFKA_RESULT_TOPIC]
    missing_topics = []

    for topic in required_topics:
        if topic in topics:
            print(f"  ✓ {topic} - 存在")
            # 获取 topic 详情
            metadata = admin_client.describe_topics([topic])
            for t in metadata:
                partitions = len(t['partitions'])
                print(f"    分区数: {partitions}")
        else:
            print(f"  ✗ {topic} - 不存在")
            missing_topics.append(topic)

    # 创建缺失的 topics
    if missing_topics:
        print(f"\n4️⃣ 创建缺失的 Topics...")
        new_topics = [
            NewTopic(name=topic, num_partitions=1, replication_factor=1)
            for topic in missing_topics
        ]
        try:
            result = admin_client.create_topics(new_topics, validate_only=False)
            for topic, future in result.items():
                try:
                    future.result()  # 等待创建完成
                    print(f"  ✓ {topic} 创建成功")
                except Exception as e:
                    print(f"  ✗ {topic} 创建失败: {e}")
        except Exception as e:
            print(f"  ✗ 创建 topics 失败: {e}")

    admin_client.close()

except Exception as e:
    print(f"✗ Kafka 连接失败: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("\n5️⃣ 测试 Consumer 连接...")

# 测试 Processor Consumer
print(f"\nProcessor Consumer ({config.KAFKA_PROCESSOR_GROUP_ID}):")
try:
    consumer = KafkaConsumer(
        config.KAFKA_TASK_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','),
        group_id=config.KAFKA_PROCESSOR_GROUP_ID,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        consumer_timeout_ms=2000
    )

    # 等待分区分配
    print("  等待分区分配...")
    time.sleep(3)

    partitions = consumer.assignment()
    if partitions:
        print(f"  ✓ 已分配分区: {partitions}")
    else:
        print(f"  ✗ 未分配到任何分区")
        print(f"  提示: Topic '{config.KAFKA_TASK_TOPIC}' 可能不存在或没有分区")

    consumer.close()

except Exception as e:
    print(f"  ✗ Consumer 创建失败: {e}")

# 测试 Uploader Consumer
print(f"\nUploader Consumer ({config.KAFKA_UPLOADER_GROUP_ID}):")
try:
    consumer = KafkaConsumer(
        config.KAFKA_RESULT_TOPIC,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','),
        group_id=config.KAFKA_UPLOADER_GROUP_ID,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        consumer_timeout_ms=2000
    )

    # 等待分区分配
    print("  等待分区分配...")
    time.sleep(3)

    partitions = consumer.assignment()
    if partitions:
        print(f"  ✓ 已分配分区: {partitions}")
    else:
        print(f"  ✗ 未分配到任何分区")
        print(f"  提示: Topic '{config.KAFKA_RESULT_TOPIC}' 可能不存在或没有分区")

    consumer.close()

except Exception as e:
    print(f"  ✗ Consumer 创建失败: {e}")

print("\n" + "=" * 60)
print("\n✅ 检查完成！")
print("\n如果发现问题，请:")
print("  1. 确保 Kafka 正在运行")
print("  2. 确保 topics 已创建并有分区")
print("  3. 重启服务: ./stop_local.sh && ./start_local.sh")
print("=" * 60)

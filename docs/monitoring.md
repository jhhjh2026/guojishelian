# Monitoring

## 1. 日志
- 文件日志默认写入 `logs/`
- 日志格式可在 `backend/app/utils/logger.py` 扩展为 JSONL，便于 Loki/ELK 采集。

## 2. 指标
- Prometheus 格式：`GET /api/metrics`

建议补充指标：
- request latency / QPS / error rate
- cache hit/miss
- rerank latency
- vector store load time

## 3. 健康检查
- `GET /api/health`：应用存活
- `GET /api/ready`：依赖就绪（数据库连通性）

## 4. 告警
- QPS/错误率异常
- 向量库/LLM/Embedding 调用失败率
- 磁盘/内存使用率

## 5. 集成建议
- 使用 Prometheus + Grafana
- 日志接入 Loki 或 ELK
- 关键接口设置 latency/error 告警阈值

# TECHNICAL_SUMMARY.md — ISSF 2026 规则问答系统技术总结

## 1. 项目概述
本项目是一个基于 **LangChain** 构建的 RAG（检索增强生成）问答系统，面向 **ISSF（国际射击运动联合会）2026 新版射击规则**提供精准问答能力。系统通过向量化、两阶段检索（粗召回 + 精排重排）以及 LLM 生成，实现规则自动问答，并配套管理后台与 JSON API。

核心目标：
- 面向 ISSF 规则场景的领域问答
- 答案简洁精准，数值/时间/距离原文引用
- 两阶段检索：粗召回 → qwen3-vl-rerank 精排 → LLM 生成
- 生产可用：支持缓存（Redis/LRU）、重试、日志、向量库自动维护

---


---

## 3. 技术栈

| 类别 | 技术/库 | 版本/说明 |
|------|---------|-----------|
| LLM | 通义千问（qwen-max） | 通过 DashScope API 接入 |
| Embedding | text-embedding-v4 | 阿里云 DashScope 嵌入模型 |
| Reranker | qwen3-vl-rerank | 两阶段检索精排模型 |
| 向量数据库 | Chroma（langchain-chroma） | 本地持久化，chromadb==0.5.23 |
| 大模型框架 | LangChain 0.3.x | 核心编排、Prompt 管理 |
| Web 框架 | FastAPI | REST API + SSE 流式 |
| 前端 | Vue 3 + Vite + Element Plus + ECharts | 按需引入 + 代码拆分 |
| 数据库 | SQLite / MySQL（可切换） | SQLAlchemy 2.x |
| 缓存 | Redis（可选）+ 进程内 LRU 降级 | 多 worker 共享 |
| 认证 | JWT + RBAC + 审计 | 7 个细粒度权限位 + admin 超级位 |

---

## 4. RAG 检索链路

1. **输入过滤**：问候语/乱码/空输入 → 固定回复
2. **同义词扩展**：227 词条，max_expanded_terms=5
3. **向量粗召回**：text-embedding-v4 → Chroma Top-K=10
4. **精排重排**：qwen3-vl-rerank → Top-N=3
5. **LLM 生成**：qwen-max，temperature=0，Prompt 硬约束
6. **输出校验**：sanitize_answer 剔除追溯性表述、emoji
7. **缓存落库**：Redis/LRU + QA 历史

### Prompt 硬约束
- 直接给结论，3–5 句，禁止"总述→分项→总结"
- 数值/时间/距离原文引用，不得篡改
- 禁止"文档1/2/3""参考文档""上下文"等追溯性表述
- 仅在上下文完全无相关信息时才拒答

---

## 5. 权限模型

| 权限常量 | 含义 | 适用端点 |
|---------|------|---------|
| rules:read | 查看规则列表 | GET /admin/rules |
| rules:manage | 规则增删改 | POST/PUT/DELETE /admin/rules |
| rules:import | 文档导入 | POST /admin/rules/import |
| users:manage | 用户管理 | GET/POST/PUT /admin/users |
| roles:manage | 角色管理 | 角色相关端点 |
| index:manage | 索引重建/缓存清空 | POST /admin/index/rebuild |
| stats:view | 查看看板 | GET /admin/dashboard |
| admin | 超级管理员（兼容旧代码） | 自动通过所有检查 |

---

## 6. 缓存策略
- **Redis**：配置 REDIS_URL 时启用，多 worker 共享，TTL=3600s
- **LRU 降级**：未配置 Redis 时自动降级为进程内 LRU（容量 128）
- 缓存键含模型指纹，换模型自动失效
- DEPLOYMENT.md 已标注多 worker 需 Redis 的约束

---

## 7. 长文档章节拆分
- doc_parser.py 新增 `split_markdown_by_headings`
- 上传接口支持 files 多选 + split 拆分开关
- 自动按 Markdown 标题（#/##/###）拆分，超大段按段落二次拆分
- 前端支持批量上传

---

## 8. 关键特性总结

| 特性 | 实现 | 说明 |
|------|------|------|
| 两阶段检索 | 向量召回 + qwen3-vl-rerank | 兼顾召回率与精确率 |
| 查询增强 | expand_query_synonyms | 227 词条同义词扩展 |
| 输出校验 | sanitize_answer | 剔除追溯表述/emoji |
| 缓存 | Redis + LRU 降级 | 多 worker 一致性 |
| 权限 | 7 个细粒度 + admin 超级位 | RBAC |
| 前端优化 | Element Plus 按需 + manualChunks | 首屏 ~35KB gzip |
| 容器化 | 三阶段 Dockerfile + 非 root | 健康检查 |
| 评测 | eval_rag.py 三种模式 | dry-run/retrieval/full |
| lifespan | 异步上下文管理器 | 替代废弃 @app.on_event |

---

## 9. 当前已知限制
- 向量库为本地 Chroma 单机（P1-2 中期项）
- 不支持旧版 .doc / 扫描件 OCR
- 前端未做 i18n（中文硬编码）
- 找回密码未接邮件服务
- 无 Hybrid Search（向量+BM25）
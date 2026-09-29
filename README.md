# ISSF 2026 射击规则问答助手

基于 LangChain + FastAPI 的检索增强问答系统，面向 ISSF 2026 新版射击规则提供精准问答、知识库管理与管理后台。

## 功能特性
- 规则问答：SSE 流式/普通问答、缓存、重排
- 知识库管理：规则 CRUD、版本管理、结构化元数据
- 用户与权限：JWT 认证、RBAC 角色权限
- 管理后台：规则管理、看板统计、审计日志
- 合规与监控：敏感词过滤、审计日志、/metrics 指标、健康检查
- 部署：Docker / docker-compose、GitHub Actions CI

## 快速开始

### 1. 环境准备
- Python 3.10 ~ 3.13
- 虚拟环境：`python -m venv .venv && .\.venv\Scripts\activate`

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
复制 `.env_template.txt` 为 `.env`，并填写 `DASHSCOPE_API_KEY`。

### 4. 初始化数据库与种子数据
```bash
python scripts/seed_db.py
```

### 5. 构建索引
```bash
python -m backend.app.ingest
# 规则更新后强制重建
python -m backend.app.ingest --rebuild
```

### 6. 运行项目

#### Web 服务（FastAPI）
```bash
# 方式一：直接运行模块
python -m backend.app.server

# 方式二：uvicorn
uvicorn backend.app.server:app --host 0.0.0.0 --port 8000
```

#### 前端页面（Vue3 + Vite + TS）
```bash
cd frontend
npm install
npm run dev
```

## 项目结构
```
frontend/
  package.json
  index.html
  src/
    main.ts
    App.vue
    api/index.ts
    router/index.ts
    views/Ask.vue
    views/Login.vue
    views/Layout.vue
    views/admin/Rules.vue
    views/admin/Users.vue
    views/admin/Dashboard.vue
    utils/detection-service.ts
backend/
  app/
    config.py           # 配置中心（Pydantic Settings）
    server.py           # FastAPI 入口
    routes.py           # 路由聚合
    routers/
      auth.py           # 认证路由
      rules.py          # 规则查询路由
      admin.py          # 管理后台路由
      system.py         # 系统健康/版本路由
    core/rag_service.py # RAG 核心逻辑
    db/
      database.py       # 数据库会话管理
      models.py         # ORM 模型
      migrations/       # Alembic 迁移
    schemas/
      auth.py
      rule.py
      audit.py
    services/
      auth_service.py   # 认证服务
      audit_service.py  # 审计日志
      moderation.py     # 内容安全
      stats_service.py  # 看板统计
    utils/
      security.py       # JWT/权限
      metrics.py        # 指标收集
      logger.py
  tests/
    test_server.py
    test_integration.py
    test_imports.py
    conftest.py
data/
  rules/
  isf.db               # SQLite 数据库（默认）
scripts/
  seed_db.py           # 初始化数据库与种子数据
  backup.py            # 备份脚本
docs/
  api.md
requirements.txt
.env
Dockerfile
docker-compose.yml
README.md
DEPLOYMENT.md
```

## 接口文档
详见 `docs/api.md`

核心接口：
- `POST /api/auth/login`
- `POST /api/ask`
- `GET /api/rules`
- `GET /api/admin/rules`
- `POST /api/admin/rules`
- `PUT /api/admin/rules/{rule_id}`
- `DELETE /api/admin/rules/{rule_id}`
- `GET /api/admin/dashboard`
- `GET /api/metrics`

## 管理后台
- 默认管理员账号：`admin / admin123`
- 访问后台需要 `/api/auth/login` 获取 JWT，并在后续请求携带 `Authorization: Bearer <token>`

## 当前进度与测试
- 当前测试状态：27 passed, 1 skipped, 2 failed
- `backend/tests/test_admin_integration.py` 集成测试中 admin 路由的依赖注入暂未跑通，已明确跳过，待后续补齐服务启动基座后恢复。

```bash
pytest backend/tests -v
```

## 常见问题
如遇问题请查阅 `DEPLOYMENT.md`。

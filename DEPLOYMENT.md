# DEPLOYMENT.md - ISSF RAG 部署文档

## 环境要求
- Python 3.10 ~ 3.11（推荐 3.11）
- 系统：Windows / macOS / Linux（当前已验证 Windows + Python venv）

## 快速部署

### 1. 克隆项目
```bash
git clone <仓库地址>
cd issf-rag-assistant
```

### 2. 创建并激活虚拟环境
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
# 国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 配置环境变量
复制 `.env_template.txt` 为 `.env`，并填入：
```dotenv
DASHSCOPE_API_KEY=sk-xxxxxxxx
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v2
RERANK_ENABLED=true
RERANK_MODEL=gte-rerank-v2
RERANK_TOP_N=3
RETRIEVER_TOP_K=10
CACHE_CAPACITY=128
CACHE_TTL_SECONDS=3600
```

### 5. 准备规则文档
将 ISSF 规则 Markdown 文件放入 `data/rules/`（支持多层子目录）。
```bash
mkdir -p data/rules
# 将规则 .md 文件放入该目录
```

### 6. 构建向量索引
```bash
# 首次构建
python -m backend.app.ingest

# 强制重建（规则文档有更新时使用）
python -m backend.app.ingest --rebuild
```

### 7. 启动服务

#### 命令行交互（CLI）
```bash
python -m backend.app.cli
```

#### HTTP 服务（FastAPI）
```bash
# 直接运行模块
python -m backend.app.server

# 或通过 uvicorn
uvicorn backend.app.server:app --host 0.0.0.0 --port 8000

# 兼容入口
python run.py
```

访问：
- `POST http://localhost:8000/api/ask` body: `{"question":"...", "use_cache":true}`
- `GET http://localhost:8000/api/health`

#### 前端页面（静态单页）
- 方式一：直接用浏览器打开 `frontend/index.html`
- 方式二：启动 HTTP 服务后访问 `http://localhost:8000/`

---

## 常见问题排查

### API Key 无效
- 检查 `.env` 中 `DASHSCOPE_API_KEY` 是否正确
- 确认密钥具备模型调用和 Embedding 权限

### 向量库加载失败
- 删除旧索引并重建：`python -m backend.app.ingest --rebuild`
- 检查 `data/vector_store/` 目录权限

### 重排模型调用失败
- 确认 `RERANK_ENABLED=true` 且 API Key 有效
- 可暂时关闭重排：设置 `RERANK_ENABLED=false`，系统将回退到向量库原始排序

### 依赖安装失败
- 优先使用国内镜像：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
- Python 版本建议 3.11，避免 3.12+ 兼容性问题

## 压测与评测
```bash
# 自动化评测
python data/test_runner.py

# 压力测试（20轮，默认0.3秒间隔）
python scripts/stress_test.py --rounds 20 --sleep 0.3
```

# QT-Agent

<p align="center">
  <strong>千通 AI 智能助手</strong> — 基于 LangGraph 的企业级 RAG 智能体平台
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.116-009688.svg" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-0.6-ff9800.svg" alt="LangGraph" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
</p>

---

## 项目简介

QT-Agent 是一个从零构建的企业级 AI 智能体平台，核心基于 **LangGraph** 编排多步推理工作流，集成 **RAG 检索增强生成**、**多模态知识入库**、**联网搜索降级**、**三层上下文记忆**、**Skill 模块化扩展**、**MCP 工具桥接** 等能力，提供完整的「文档上传 → 解析切块 → 向量入库 → 智能问答」闭环。

### 核心特性

- 🧠 **LangGraph 多步推理主图** — Supervisor 路由器自动决策（闲聊 / 知识问答 / 联网搜索 / Skill 调用）
- 📚 **RAG 检索闭环** — 向量召回 → 重排 → 相关性评估 → 循环 recall → 带 Citation 回答
- 🌐 **WebSearch 降级路径** — 知识库低命中自动降级联网搜索，带清晰来源提示
- 📄 **多模态知识入库** — 支持 TXT / Markdown / PDF / 图片，OCR fallback，异步管道
- 💬 **SSE 流式输出** — 实时流式返回 LLM 生成内容，支持指数退避重试
- 🧩 **三层记忆架构** — 摘要层 + 近期窗口 + Redis 热缓存，支持超长对话
- 🔍 **两级缓存命中** — 精确匹配 + 语义相似度匹配，重复问题秒级响应
- 🏭 **Provider 工厂模式** — LLM / Embedding / Search / Parser 统一抽象，可插拔切换
- 🛠️ **Skill 模块化** — 可注册自定义 Skill（知识库问答 / Web 搜索 / MCP 工具调用），动态接入主图
- 🔌 **MCP 桥接** — 将外部 MCP 工具适配为 LangGraph 节点，统一工具调用协议
- 📊 **可观测性** — 图执行全链路 trace_id / request_id 贯穿，结构化日志 + 审计记录
- 🧪 **端到端测试** — API 端点冒烟测试 + 审计服务单元测试 + 运行时并发测试

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI API Layer                         │
│  /chat  │  /ingest/upload  │  /knowledge-bases  │  /users       │
└───┬────────────┬──────────────────┬──────────────────┬───────────┘
    │            │                  │                  │
┌───▼────────────▼──────────────────▼──────────────────▼───────────┐
│               ChatService / IngestionService / UsersService      │
└───┬──────────────────────────────────────────────────────────────┘
    │
┌───▼──────────────────────────────────────────────────────────────┐
│                     LangGraph Main Graph                          │
│                                                                    │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐           │
│  │  init     │─▶│ load_session │─▶│ check_window_cache│           │
│  │  request  │  │   context    │  │  (精确+语义匹配)   │           │
│  └──────────┘  └──────────────┘  └────────┬─────────┘           │
│                                              │                     │
│                                     ┌────────▼────────┐           │
│                                     │   supervisor    │           │
│                                     │     route       │           │
│                                     └─┬────┬────┬────┐│           │
│                                ┌──────┘    │    │    └──────┐│   │
│                                ▼           ▼    │           ▼│   │
│                          ┌─────────┐ ┌────────┐ │  ┌──────────┐│
│                          │smalltalk│ │  RAG   │ │  │  Skill   ││
│                          │         │ │ 子图   │ │  │  子图    ││
│                          └────┬────┘ └───┬────┘ │  └─────┬────┘│
│                               │          │fallback      │      │
│                               │    ┌─────▼──────────────▼──┐  │
│                               │    │   WebSearch 子图       │  │
│                               │    │   (search → clean →   │  │
│                               │    │    answer_by_web)      │  │
│                               │    └──────────┬────────────┘  │
│                               │               │                │
│                          ┌────▼───────────────▼────────────┐   │
│                          │    post_process → persist_state  │   │
│                          └──────────────┬──────────────────┘   │
│                                         ▼                       │
│                                        END                      │
└──────────────────────────────────────────────────────────────────┘
    │              │              │              │              │
┌───▼────┐  ┌─────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐ ┌────▼─────┐
│PostgreSQL│ │   Redis    │ │  Milvus  │ │   MinIO    │ │ Audit Log│
│(会话/消息│ │(热缓存/窗口)│ │(向量存储)│ │(文件存储)  │ │(操作审计) │
│/元数据)  │ │            │ │          │ │            │ │          │
└─────────┘ └────────────┘ └──────────┘ └────────────┘ └──────────┘
```

### RAG 子图流程

```
rag_prepare → recall_documents → rerank_documents → evaluate_relevance
     │                                              │
     │              ┌───────────────────────────────┘
     │              │ (relevance < threshold)
     │         reform_query
     │              │ (recall_count < max)
     └──────────────┘
                    │ (relevance ≥ threshold)
              answer_by_rag
                    │
              fallback_to_websearch (可选降级)
```

### Skill 子图流程

```
resolve_skill → skill_executor → END
     │               │
     │ (未注册)       │ (已注册: knowledge_qa / web_search / mcp_tool)
     ▼               ▼
skill_unavailable   对应 Skill 执行
```

### 三层记忆架构

| 层级 | 存储 | 说明 |
|------|------|------|
| 摘要层 (Summary) | PostgreSQL sessions.metadata | 早期历史经 LLM 压缩为 ≤500 字摘要 |
| 近期窗口 (Recent) | PostgreSQL messages | 最近 10 条原始消息，LLM 直接可见 |
| 热缓存 (Hot) | Redis | 最近 20 条消息，快速会话恢复 |

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **Web 框架** | FastAPI 0.116 + Uvicorn |
| **AI 编排** | LangGraph 0.6 |
| **LLM** | 智谱 GLM-4-Flash（可切换） |
| **Embedding** | BGE-M3（1024 维） |
| **向量数据库** | Milvus 2.6 |
| **关系数据库** | PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic |
| **缓存** | Redis 7 |
| **对象存储** | MinIO |
| **文档解析** | PyMuPDF (PDF) + Tesseract OCR |
| **联网搜索** | Tavily Search API |
| **配置管理** | pydantic-settings |
| **容器化** | Docker + Docker Compose |

---

## 项目结构

```
QT-Agent/
├── app/
│   ├── api/v1/               # API 路由层
│   │   ├── routes/
│   │   │   ├── chat.py       # 聊天接口（SSE 流式 + 非流式）
│   │   │   ├── health.py     # 健康检查
│   │   │   ├── ingestion.py  # 知识库管理 + 文档上传
│   │   │   └── users.py      # 用户管理接口
│   │   └── router.py         # 路由注册
│   ├── core/
│   │   ├── config.py         # 统一配置（pydantic-settings）
│   │   └── logging.py        # 结构化日志 + 纯 ASGI 请求中间件
│   ├── db/                   # 数据库层
│   │   ├── models.py         # SQLAlchemy ORM 模型
│   │   └── session.py        # 异步引擎/会话管理
│   ├── graph/                # LangGraph 图编排
│   │   ├── builder.py        # 主图编译器
│   │   ├── nodes.py          # 主图节点（含自管理 session 版本）
│   │   ├── state.py          # GraphState 定义
│   │   ├── rag_builder.py    # RAG 子图
│   │   ├── rag_nodes.py      # RAG 节点
│   │   ├── web_builder.py    # WebSearch 子图
│   │   ├── web_nodes.py      # WebSearch 节点
│   │   ├── skill_builder.py  # Skill 子图
│   │   ├── skill_nodes.py    # Skill 节点
│   │   └── observability.py  # 图执行可观测性
│   ├── ingestion/            # 多模态入库管道
│   │   ├── pipeline.py       # 入库管道（解析→切块→Embedding→Milvus）
│   │   └── chunker.py        # 智能文本切块
│   ├── memory/               # 上下文记忆
│   │   ├── history_loader.py # Redis→PostgreSQL 历史恢复
│   │   ├── checkpointer.py   # LangGraph PostgreSQL Checkpointer
│   │   ├── window_cache.py   # 两级缓存命中
│   │   └── summary_memory.py # 三层记忆 + LLM 摘要
│   ├── mcp/                  # MCP 工具桥接
│   │   ├── client.py         # MCP 客户端抽象
│   │   ├── registry.py       # MCP 工具注册表
│   │   └── tool_adapter.py   # MCP→LangGraph 工具适配器
│   ├── providers/            # AI Provider 抽象层
│   │   ├── base.py           # BaseLLM / BaseEmbedding / BaseSearch / BaseParser
│   │   ├── glm.py            # GLM-4-Flash 实现（含 429 重试 + 流式修复）
│   │   ├── default_embedding.py  # BGE-M3 Embedding 实现
│   │   ├── mock.py           # Mock Provider（开发环境降级）
│   │   ├── web_search.py     # Tavily 搜索实现
│   │   ├── factories.py      # Provider 工厂
│   │   └── parsers/          # 文档解析器
│   │       ├── text_parser.py
│   │       ├── pdf_parser.py
│   │       └── image_parser.py
│   ├── repositories/         # 数据访问层
│   │   ├── chat.py           # 会话/消息/用户/checkpoint 仓库
│   │   └── knowledge.py      # 知识库/文档仓库
│   ├── retrieval/            # 向量检索模块
│   │   ├── retriever.py      # 统一检索入口
│   │   ├── milvus_store.py   # Milvus 向量存储
│   │   ├── access.py         # 检索权限控制
│   │   └── base.py           # 检索基类/数据模型
│   ├── schemas/              # Pydantic Schema
│   │   ├── chat.py           # 聊天请求/响应/调试
│   │   ├── ingestion.py      # 入库请求/响应
│   │   ├── knowledge.py      # 知识库/文档 Schema
│   │   ├── provider.py       # LLM/Embedding 消息与响应
│   │   └── user.py           # 用户 Schema
│   ├── services/             # 业务服务层
│   │   ├── chat.py           # 聊天服务（含 SSE 流式 + 异常兜底）
│   │   ├── ingestion.py      # 入库服务（异步管道编排）
│   │   ├── knowledge.py      # 知识库服务
│   │   ├── users.py          # 用户服务
│   │   ├── audit.py          # 审计服务
│   │   ├── background_tasks.py  # 后台任务管理
│   │   └── object_storage.py # MinIO 对象存储
│   ├── skills/               # Skill 模块化扩展
│   │   ├── base.py           # BaseSkill 抽象
│   │   ├── registry.py       # Skill 注册表
│   │   ├── schemas.py        # Skill Schema
│   │   ├── knowledge_qa.py   # 知识库问答 Skill
│   │   ├── web_search.py     # Web 搜索 Skill
│   │   ├── mcp_tool.py       # MCP 工具 Skill
│   │   ├── policy_compare/   # 政策对比 Skill（示例）
│   │   └── report_analysis/  # 报告分析 Skill（示例）
│   ├── cache/                # Redis 缓存
│   ├── utils/                # 工具函数
│   │   └── runtime.py        # 运行时并发/超时控制
│   ├── lifecycle.py          # 应用生命周期
│   └── main.py               # FastAPI 入口
├── alembic/                  # 数据库迁移
├── dashboard/                # 前端调试台（React + Vite）
├── docker/                   # Docker 辅助文件
├── scripts/                  # 运维与测试脚本
│   ├── start.sh              # 容器启动入口
│   ├── wait_for_dependencies.py  # 依赖等待
│   ├── init_db.py            # 数据库初始化
│   ├── init_milvus.py        # Milvus 集合初始化
│   ├── seed_demo_data.py     # 演示数据播种
│   ├── ingest_test_data.py   # 测试文档注入
│   ├── test_api.py           # API 端点冒烟测试
│   └── test_data/            # 测试文档
├── tests/                    # 自动化测试
│   ├── test_audit_service.py # 审计服务测试
│   ├── test_chat_api_e2e.py  # Chat API 端到端测试
│   └── test_runtime.py       # 运行时并发测试
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── alembic.ini
```

---

## 部署与初始化

### 环境要求

- Docker Desktop 或 Docker Engine + Docker Compose
- Python 3.12+（仅在你需要离线读代码或跑纯本地脚本时使用，日常运行推荐全部走 Docker）

### 推荐启动方式：Docker Compose

```bash
# 1. 进入项目目录
cd QT-Agent

# 2. 复制环境变量模板
cp .env.example .env

# 3. 按需编辑 .env
# 至少建议关注：
#   LLM__API_KEY=your_zhipu_api_key
#   WEB_SEARCH__API_KEY=your_tavily_api_key
#   APP__ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

# 4. 构建并启动服务
docker compose up --build -d

# 5. 执行数据库迁移
docker compose exec app alembic upgrade head

# 6. 初始化数据库结构与 Milvus 集合
docker compose exec app python scripts/init_db.py
docker compose exec app python scripts/init_milvus.py

# 7. 播种演示数据（可选，但建议调试页联调时执行）
docker compose exec app python scripts/seed_demo_data.py

# 8. 验证服务
curl -s http://localhost:8000/health
```

### 初始化脚本说明

| 脚本 | 作用 | 推荐执行时机 |
|------|------|-------------|
| `scripts/init_db.py` | 执行数据库连通检查并创建 ORM 表结构 | 首次启动、测试环境重建 |
| `scripts/init_milvus.py` | 初始化 Milvus collection 与索引 | 首次启动、Milvus 数据卷重置后 |
| `scripts/seed_demo_data.py` | 写入演示用户、知识库、文档和示例会话 | 联调 API、调试页、发布验收前 |
| `scripts/ingest_test_data.py` | 注入测试 MD 文档到 RAG 知识库 | API 端点功能验证 |
| `scripts/test_api.py` | 自动化 API 端点冒烟测试（8 项） | 发布验收、CI 冒烟 |

### 本地开发方式

项目默认按容器化方式运行。若只想在本地前端联调，可保持后端运行在 Docker 中，再单独启动前端：

```bash
# 后端仍在 Docker 中
docker compose up -d app postgres redis minio milvus etcd

# 前端本地调试
cd dashboard
npm install
npm run dev
```

默认情况下，调试页会访问 `http://localhost:8000`，适合"浏览器在宿主机、后端在 Docker 容器"这一联调方式。

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| QT-Agent API | 8000 | FastAPI 主服务 |
| PostgreSQL | 5432 | 关系数据库 |
| Redis | 6379 | 缓存服务 |
| MinIO API | 9000 | 对象存储 |
| MinIO Console | 9001 | MinIO 管理界面 |
| Milvus | 19530 | 向量数据库 |
| etcd | 2379 | Milvus 元数据存储 |

---

## API 接口文档

启动服务后访问 Swagger 文档：`http://localhost:8000/docs`

### User API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/users` | 创建用户 |
| `GET` | `/api/v1/users` | 列出用户 |
| `GET` | `/api/v1/users/{user_id}` | 查询用户详情 |

**请求示例：**

```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo_user",
    "display_name": "Demo User",
    "email": "demo_user@example.com"
  }'
```

### Chat API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/chat` | 发送消息（支持 `stream=true` SSE 流式） |
| `GET` | `/api/v1/chat/history?session_id=xxx` | 查询会话历史 |
| `GET` | `/api/v1/chat/debug?session_id=xxx` | 查询调试详情、checkpoint、timeline、工具调用 |

**请求示例：**

```bash
# 非流式
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo_user",
    "message": "什么是RAG？",
    "stream": false
  }'

# 流式（SSE）
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo_user",
    "message": "介绍一下人工智能的发展历史",
    "stream": true
  }'

# 指定路由模式
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo_user",
    "message": "格力电器有哪些核心技术？",
    "stream": false,
    "route_mode": "knowledge"
  }'
```

### Knowledge Base API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/knowledge-bases` | 创建知识库 |
| `GET` | `/api/v1/knowledge-bases` | 列出知识库 |
| `POST` | `/api/v1/ingest/upload` | 上传文档并触发入库 |
| `GET` | `/api/v1/documents/{doc_id}/status` | 查询文档入库状态 |
| `GET` | `/api/v1/documents/{doc_id}` | 查询文档详情 |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/documents` | 列出知识库下的文档 |
| `POST` | `/api/v1/knowledge-bases/{kb_id}/search-debug` | 调试向量检索与权限过滤 |

**入库示例：**

```bash
# 先创建用户，拿到返回中的 id
USER_ID="<real_user_uuid>"

# 创建知识库（知识库接口要求传真实 user UUID）
curl -X POST "http://localhost:8000/api/v1/knowledge-bases?user_id=${USER_ID}" \
  -H "Content-Type: application/json" \
  -d '{"name": "产品文档", "description": "产品相关技术文档"}'

# 上传文档
curl -X POST "http://localhost:8000/api/v1/ingest/upload?user_id=${USER_ID}" \
  -F "knowledge_base_id=<kb_id>" \
  -F "file=@document.pdf"

# 查询入库状态
curl "http://localhost:8000/api/v1/documents/<doc_id>/status?user_id=${USER_ID}"

# 调试检索结果
curl -X POST http://localhost:8000/api/v1/knowledge-bases/<kb_id>/search-debug \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"研发资料里提到哪些能力\",
    \"user_id\": \"${USER_ID}\",
    \"top_k\": 3
  }"
```

### Health Check

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 服务健康检查 |

---

## 环境变量配置

所有配置通过 `.env` 文件管理，使用 `__` 双下划线表示嵌套层级。完整样例见 `.env.example`。

### 运行时最常用配置

```bash
# ─── 应用配置 ───
APP__ENV=development
APP__DEBUG=true
APP__HOST=0.0.0.0
APP__PORT=8000
APP__API_PREFIX=/api/v1
APP__ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

# ─── 数据库 / 缓存 / 向量库 / 对象存储 ───
DB__HOST=postgres
DB__PORT=5432
DB__NAME=qt_agent
DB__USER=qt_agent
DB__PASSWORD=qt_agent
REDIS__HOST=redis
MILVUS__HOST=milvus
MINIO__ENDPOINT=minio:9000

# ─── LLM / Embedding / WebSearch ───
LLM__PROVIDER=glm
LLM__MODEL=glm-4-flash
LLM__API_KEY=
EMBEDDING__PROVIDER=default
EMBEDDING__MODEL=bge-m3
EMBEDDING__DIMENSION=1024
WEB_SEARCH__PROVIDER=tavily
WEB_SEARCH__API_KEY=

# ─── 稳定性与降级 ───
RUNTIME__EMBEDDING_MAX_CONCURRENCY=2
RUNTIME__EMBEDDING_TIMEOUT_SECONDS=60
RUNTIME__OBJECT_STORAGE_TIMEOUT_SECONDS=30
RUNTIME__BACKGROUND_TASK_TIMEOUT_SECONDS=1800
RUNTIME__REDIS_REQUIRED_ON_STARTUP=false
RUNTIME__MINIO_REQUIRED_ON_STARTUP=false
```

### 配置建议

- 开发联调时可不填 `LLM__API_KEY`，系统会在非生产环境下降级到 mock provider，保证主流程可跑通。
- 如果你本地运行调试页，记得把 `APP__ALLOWED_ORIGINS` 加上 `http://localhost:5173`。
- 生产环境建议收紧 `APP__ALLOWED_ORIGINS`，并显式配置真实的 LLM / WebSearch 密钥。

## 运维与发布检查

### 发布前推荐命令

```bash
# 1. 构建并启动
docker compose up -d --build

# 2. 执行迁移与初始化
docker compose exec app alembic upgrade head
docker compose exec app python scripts/init_db.py
docker compose exec app python scripts/init_milvus.py

# 3. 播种演示数据（可选）
docker compose exec app python scripts/seed_demo_data.py

# 4. 健康检查
curl -s http://localhost:8000/health

# 5. API 冒烟测试
python scripts/test_api.py

# 6. 自动化测试
pytest tests/
```

### 默认发布验收项

- 镜像可构建：`docker compose build`
- Compose 可启动：`docker compose up -d`
- 数据库迁移可执行：`docker compose exec app alembic upgrade head`
- API 冒烟测试通过：`python scripts/test_api.py`（8/8）
- 默认模型链路可运行：未配置真实密钥时，开发环境可走 mock provider
- 检索链路可运行：`seed_demo_data.py` 会初始化知识库并写入向量，可直接用于 `search-debug`

## 常见故障排查

### 1. `knowledge-bases` 接口返回 403 或查不到数据

- 知识库和文档接口按真实用户 UUID 做权限隔离。
- `POST /api/v1/users` 返回的 `id` 才是后续 `user_id` 查询参数应该使用的值。
- 聊天接口要求传 `username`，服务会自动补齐对应的内部 `user_id`。
- 知识库相关接口请优先使用真实 UUID 形式的 `user_id`。

### 2. Docker 已启动，但 Milvus 检索无结果

- 先执行 `docker compose exec app python scripts/init_milvus.py`
- 再执行 `docker compose exec app python scripts/seed_demo_data.py`
- 如果是新环境，确认 `MILVUS__COLLECTION` 没有被改成旧 collection 名称

### 3. 文档上传成功，但一直停留在 `processing`

- 查看应用日志：`docker compose logs -f app`
- 正常情况下会看到 `ingestion.parse_done`、`ingestion.embedding_done`、`ingestion.milvus_upsert_done`
- 如果 MinIO 不可用，上传接口会返回 `503`
- 如果 embedding 或模型超时，日志里会带 `timeout` 与对应节点事件

### 4. 调试页打开了，但请求失败或浏览器报跨域

- 确认后端容器已对宿主机暴露 `8000`
- 确认 `.env` 中 `APP__ALLOWED_ORIGINS` 包含 `http://localhost:5173`
- 调试页默认访问 `http://localhost:8000`，适用于"前端本地、后端 Docker"模式

### 5. 没有配置外部模型密钥，聊天还能不能跑

- 可以。开发环境下未配置 `LLM__API_KEY` 时会自动回退到 mock provider
- 这适合接口联调、图调试和前端开发，但不代表真实生产回答质量

### 6. SSE 流式请求返回 `ReadError`

- 已在 GLMProvider 中修复：使用标准 `async with client.stream(...)` 模式替代自定义 context manager
- 确保 `LLMMessage` 序列化时不包含空的 `metadata` 字段（GLM API 对此敏感）
- 如果仍然出现，检查网络环境是否稳定，GLM API 是否限流

### 7. asyncpg 报 `CancelledError`

- 已通过将请求日志中间件从 `BaseHTTPMiddleware` 重写为纯 ASGI 解决
- 此问题是 Starlette `BaseHTTPMiddleware` 的已知反模式，在客户端断开时会导致连接池异常

---

## 核心设计

### Supervisor 路由策略

Supervisor 节点根据用户输入自动决策路由：

| 路由 | 触发条件 | 处理方式 |
|------|---------|---------|
| `smalltalk` | 闲聊、问候、寒暄 | LLM 直接回复 |
| `knowledge_qa` | 知识库相关问题 | RAG 子图检索 + 生成 |
| `web_search` | 实时信息、通用问题 | Tavily 联网搜索 + LLM 总结 |
| `tool` / Skill | 工具调用意图 | Skill 子图分发执行 |
| `post_process` | 缓存命中 | 直接返回缓存结果 |

### RAG 检索增强

- **循环 Recall**：最多 2 轮，每轮重写 query 后重新检索
- **相关性评估**：基于 cosine similarity 评分判断检索结果相关度
- **重排序**：按相关性得分重排 Top-K 结果
- **Citation**：回答中标注来源文件名 + 页码 + 内容片段
- **Fallback**：低命中时自动降级到 WebSearch

### 多模态入库管道

```
文件上传 → 类型校验 → MinIO 存储 → 异步管道:
  → Parser 解析（Text/PDF/Image + OCR fallback）
  → Chunker 智能切块（字符数 + overlap + 中英文断句）
  → 批量 Embedding
  → Milvus 向量写入
  → 元数据状态更新（pending → processing → completed/failed）
```

### Skill 模块化扩展

Skill 是可插拔的功能单元，通过统一注册表动态接入主图：

| Skill | 说明 |
|-------|------|
| `knowledge_qa` | RAG 知识库问答 |
| `web_search` | 联网搜索 |
| `mcp_tool` | MCP 外部工具调用 |
| `policy_compare` | 政策对比（示例） |
| `report_analysis` | 报告分析（示例） |

### GLM Provider 稳定性设计

- **指数退避重试**：429 / 5xx / ReadTimeout 自动重试（3 次，1s → 2s → 4s）
- **流式安全**：使用标准 httpx `async with client.stream(...)` 确保 client 生命周期正确
- **Payload 清洗**：移除空 `metadata` 字段避免 GLM API 响应异常
- **Mock 降级**：未配置 API Key 时自动切换 Mock Provider

---

## 开发阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 | 项目初始化与工程骨架 | ✅ 完成 |
| P1 | 数据层与基础中间件接入 | ✅ 完成 |
| P2 | 统一抽象层与 Provider 工厂 | ✅ 完成 |
| P3 | Chat API 与 SSE 流式输出 | ✅ 完成 |
| P4 | LangGraph 主图骨架 | ✅ 完成 |
| P5 | RAG 检索闭环 | ✅ 完成 |
| P6 | 多模态知识入库 | ✅ 完成 |
| P7 | WebSearch 降级路径 | ✅ 完成 |
| P8 | 上下文管理、Checkpointer 与 Cache-Hit | ✅ 完成 |
| P9 | 用户管理与知识库权限隔离 | ✅ 完成 |
| P10 | Skill 模块化与 Supervisor 扩展 | ✅ 完成 |
| P11 | MCP 桥接层 | ✅ 完成 |
| P12 | 异步并发优化与稳定性加固 | ✅ 完成 |
| P13 | 可观测性、审计与测试 | ✅ 完成 |
| P14 | 发布准备与文档交付 | ✅ 完成 |

### 关键 Bug 修复记录

| # | 问题 | 修复 |
|---|------|------|
| 1 | PostgresCheckpointer 接口不兼容 | 修正 aput 签名、添加 aput_writes、PendingWrite 类型 |
| 2 | BaseHTTPMiddleware 导致 CancelledError | 重写为纯 ASGI 中间件 |
| 3 | 非 UUID session_id 导致 asyncpg DataError | Pydantic field_validator 前置校验 |
| 4 | LLMMessage dict/model_dump 兼容 | hasattr 检查 + 双路径处理 |
| 5 | GLM 429 限流 / ReadTimeout | 指数退避重试 + ReadError 兜底 |
| 6 | SSE 流式异常崩溃 | Exception 级兜底 + SSE error event |
| 7 | LLMConfig.timeout 字段名错误 | 修正为 timeout_seconds |
| 8 | 流式 ReadError | 标准 httpx 流式模式 + 移除空 metadata |
| 9 | logging extra 'filename' 冲突 | 改为 'file_name' |

---

## License

MIT

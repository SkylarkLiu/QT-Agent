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

QT-Agent 是一个从零构建的企业级 AI 智能体平台，核心基于 **LangGraph** 编排多步推理工作流，集成 **RAG 检索增强生成**、**多模态知识入库**、**联网搜索降级**、**三层上下文记忆** 等能力，提供完整的「文档上传 → 解析切块 → 向量入库 → 智能问答」闭环。

### 核心特性

- 🧠 **LangGraph 多步推理主图** — Supervisor 路由器自动决策（闲聊 / 知识问答 / 联网搜索）
- 📚 **RAG 检索闭环** — 向量召回 → 重排 → 相关性评估 → 循环 recall → 带 Citation 回答
- 🌐 **WebSearch 降级路径** — 知识库低命中自动降级联网搜索，带清晰来源提示
- 📄 **多模态知识入库** — 支持 TXT / Markdown / PDF / 图片，OCR fallback，异步管道
- 💬 **SSE 流式输出** — 实时流式返回 LLM 生成内容
- 🧩 **三层记忆架构** — 摘要层 + 近期窗口 + Redis 热缓存，支持超长对话
- 🔍 **两级缓存命中** — 精确匹配 + 语义相似度匹配，重复问题秒级响应
- 🏭 **Provider 工厂模式** — LLM / Embedding / Search / Parser 统一抽象，可插拔切换

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI API Layer                     │
│  /api/v1/chat  │  /api/v1/ingest/upload  │  /api/v1/knowledge-bases  │
└──────┬──────────────────────┬──────────────────────┬────────┘
       │                      │                      │
┌──────▼──────────────────────▼──────────────────────▼────────┐
│                    ChatService / IngestionService            │
└──────┬──────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                  LangGraph Main Graph                        │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │  init     │──▶│ load_session │──▶│ check_window_cache│    │
│  │  request  │   │   context    │   │    (精确+语义)    │    │
│  └──────────┘   └──────────────┘   └────────┬─────────┘    │
│                                                  │            │
│                                         ┌───────▼────────┐  │
│                                         │  supervisor    │  │
│                                         │    route       │  │
│                                         └──┬────┬────┬──┘  │
│                                    ┌───────┘    │    └─────┐│
│                                    ▼            ▼          ▼│
│                              ┌──────────┐ ┌────────┐ ┌──────┐
│                              │smalltalk │ │  RAG   │ │ Web  │
│                              │          │ │子图    │ │Search│
│                              └────┬─────┘ │        │ │ 子图 │
│                                   │       └───┬────┘ └──┬───┘
│                                   │           │fallback  │
│                                   │     ┌─────▼──────────▼┐
│                                   │     │  result_clean   │
│                                   │     │  answer_by_web  │
│                                   │     └───────┬─────────┘
│                                   │             │
│                              ┌────▼─────────────▼────┐
│                              │     post_process       │
│                              │     persist_state      │
│                              └──────────┬────────────┘
│                                         ▼
│                                        END
└─────────────────────────────────────────────────────────────┘
       │              │              │              │
  ┌────▼────┐  ┌──────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐
  │PostgreSQL│  │    Redis    │ │  Milvus  │ │   MinIO    │
  │ (会话/消息│  │(热缓存/窗口)│ │(向量存储)│ │(文件存储)  │
  │ /元数据) │  │            │ │          │ │            │
  └─────────┘  └────────────┘ └──────────┘ └────────────┘
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
│   │   │   └── ingestion.py  # 知识库管理 + 文档上传
│   │   └── router.py         # 路由注册
│   ├── core/
│   │   └── config.py         # 统一配置（pydantic-settings）
│   ├── db/                   # 数据库层
│   │   ├── models.py         # SQLAlchemy ORM 模型
│   │   └── session.py        # 异步引擎/会话管理
│   ├── graph/                # LangGraph 图编排
│   │   ├── builder.py        # 主图编译器
│   │   ├── nodes.py          # 主图节点
│   │   ├── state.py          # GraphState 定义
│   │   ├── rag_builder.py    # RAG 子图
│   │   ├── rag_nodes.py      # RAG 节点
│   │   ├── web_builder.py    # WebSearch 子图
│   │   └── web_nodes.py      # WebSearch 节点
│   ├── ingestion/            # 多模态入库管道
│   │   ├── pipeline.py       # 入库管道（解析→切块→Embedding→Milvus）
│   │   └── chunker.py        # 智能文本切块
│   ├── memory/               # 上下文记忆
│   │   ├── history_loader.py # Redis→PostgreSQL 历史恢复
│   │   ├── checkpointer.py   # LangGraph PostgreSQL Checkpointer
│   │   ├── window_cache.py   # 两级缓存命中
│   │   └── summary_memory.py # 三层记忆 + LLM 摘要
│   ├── providers/            # AI Provider 抽象层
│   │   ├── base.py           # BaseLLM / BaseEmbedding / BaseSearch / BaseParser
│   │   ├── llm.py            # GLM-4-Flash 实现
│   │   ├── embedding.py      # BGE-M3 实现
│   │   ├── web_search.py     # Tavily 搜索实现
│   │   ├── factories.py      # Provider 工厂
│   │   └── parsers/          # 文档解析器
│   │       ├── text_parser.py
│   │       ├── pdf_parser.py
│   │       └── image_parser.py
│   ├── repositories/         # 数据访问层
│   ├── retrieval/            # 向量检索模块
│   ├── schemas/              # Pydantic Schema
│   ├── services/             # 业务服务层
│   ├── cache/                # Redis 缓存
│   ├── skills/               # Skill 扩展（预留）
│   ├── mcp/                  # MCP 桥接（预留）
│   ├── utils/                # 工具函数
│   ├── lifecycle.py          # 应用生命周期
│   └── main.py               # FastAPI 入口
├── alembic/                  # 数据库迁移
├── docker/                   # Docker 辅助文件
├── scripts/                  # 启动脚本
├── tests/                    # 测试
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── alembic.ini
```

---

## 快速开始

### 环境要求

- Docker & Docker Compose
- Python 3.12+（本地开发）

### Docker Compose 一键部署

```bash
# 1. 克隆项目
git clone https://github.com/SkylarkLiu/QT-Agent.git
cd QT-Agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少配置：
#   LLM__API_KEY=your_zhipu_api_key
#   EMBEDDING__API_KEY=your_embedding_api_key  (如需)
#   WEB_SEARCH__API_KEY=your_tavily_api_key    (可选)

# 3. 启动所有服务
docker compose up --build -d

# 4. 运行数据库迁移
docker compose exec app alembic upgrade head

# 5. 验证服务
curl http://localhost:8000/health
```

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

### Chat API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/chat` | 发送消息（支持 `stream=true` SSE 流式） |
| `GET` | `/api/v1/chat/history?session_id=xxx` | 查询会话历史 |

**请求示例：**

```bash
# 非流式
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "session_id": "session_001",
    "message": "什么是RAG？",
    "stream": false
  }'

# 流式（SSE）
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "session_id": "session_001",
    "message": "介绍一下人工智能的发展历史",
    "stream": true
  }'
```

### Knowledge Base API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/knowledge-bases` | 创建知识库 |
| `GET` | `/api/v1/knowledge-bases` | 列出知识库 |
| `POST` | `/api/v1/ingest/upload` | 上传文档并触发入库 |
| `GET` | `/api/v1/documents/{doc_id}/status` | 查询文档入库状态 |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/documents` | 列出知识库下的文档 |

**入库示例：**

```bash
# 创建知识库
curl -X POST http://localhost:8000/api/v1/knowledge-bases \
  -H "Content-Type: application/json" \
  -d '{"name": "产品文档", "description": "产品相关技术文档"}'

# 上传文档
curl -X POST http://localhost:8000/api/v1/ingest/upload \
  -F "knowledge_base_id=<kb_id>" \
  -F "file=@document.pdf"

# 查询入库状态
curl http://localhost:8000/api/v1/documents/<doc_id>/status
```

### Health Check

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 服务健康检查 |

---

## 环境变量配置

所有配置通过 `.env` 文件管理，使用 `__` 双下划线表示嵌套层级：

```bash
# ─── 应用配置 ───
APP__ENV=development
APP__DEBUG=true
APP__PORT=8000

# ─── LLM 配置 ───
LLM__PROVIDER=glm
LLM__MODEL=glm-4-flash
LLM__API_KEY=your_api_key

# ─── Embedding 配置 ───
EMBEDDING__PROVIDER=default
EMBEDDING__MODEL=bge-m3
EMBEDDING__DIMENSION=1024

# ─── RAG 配置 ───
RAG__MAX_RECALL_COUNT=2
RAG__RELEVANCE_THRESHOLD=0.5
RAG__RERANK_TOP_K=3

# ─── 入库配置 ───
INGESTION__CHUNK_SIZE=512
INGESTION__CHUNK_OVERLAP=64
INGESTION__MAX_FILE_SIZE_MB=50

# ─── 联网搜索 ───
WEB_SEARCH__PROVIDER=tavily
WEB_SEARCH__API_KEY=your_tavily_key
WEB_SEARCH__MAX_RESULTS=5

# ─── 记忆配置 ───
MEMORY__WINDOW_SIZE=20
MEMORY__SUMMARY_THRESHOLD=50
MEMORY__CACHE_SIMILARITY_THRESHOLD=0.92

# ─── 数据库 ───
DB__HOST=postgres
DB__PORT=5432
DB__NAME=qt_agent
DB__USER=qt_agent
DB__PASSWORD=qt_agent
```

---

## 核心设计

### Supervisor 路由策略

Supervisor 节点根据用户输入自动决策路由：

| 路由 | 触发条件 | 处理方式 |
|------|---------|---------|
| `smalltalk` | 闲聊、问候、寒暄 | LLM 直接回复 |
| `knowledge_qa` | 知识库相关问题 | RAG 子图检索 + 生成 |
| `web_search` | 实时信息、通用问题 | Tavily 联网搜索 + LLM 总结 |
| `post_process` | 缓存命中 | 直接返回缓存结果 |

### RAG 检索增强

- **循环 Recall**：最多 2 轮，每轮重写 query 后重新检索
- **相关性评估**：LLM 判断检索结果与问题的相关度（0-1 分）
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
| P9 | 用户管理与知识库权限隔离 | ⏳ 待开发 |
| P10 | Skill 模块化与 Supervisor 扩展 | ⏳ 待开发 |
| P11 | MCP 桥接层 | ⏳ 待开发 |
| P12 | 异步并发优化与稳定性加固 | ⏳ 待开发 |
| P13 | 可观测性、审计与测试 | ⏳ 待开发 |
| P14 | 发布准备与文档交付 | ⏳ 待开发 |

---

## License

MIT

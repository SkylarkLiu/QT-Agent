# QT-Agent 智能体平台开发指南

## 项目概述

QT-Agent 是基于 LangGraph 构建的工业级 RAG 智能体平台，服务于格力百通 AI 智能助手项目。平台采用微服务架构，支持知识检索、联网搜索、多模态文档处理等功能。

## 技术栈

### 后端
- **Web框架**：FastAPI 0.115+
- **AI框架**：LangGraph、LangChain
- **数据库**：PostgreSQL 15+（主数据）、Redis 7+（缓存/热窗口）、Milvus 2.3+（向量检索）
- **对象存储**：MinIO
- **LLM提供商**：智谱GLM（glm-4-flash）、OpenAI兼容接口
- **Embedding**：BGE-M3（本地部署）或OpenAI text-embedding-3-small

### 前端
- **框架**：React 19 + TypeScript
- **UI组件**：Ant Design 5
- **构建工具**：Vite 7

### 部署
- **容器化**：Docker + Docker Compose
- **数据库迁移**：Alembic

## 系统架构

### 核心流程

```
用户请求 → FastAPI → Supervisor 路由器 → 子图执行 → 响应生成
                                    ├── knowledge_qa (RAG子图)
                                    ├── web_search (联网搜索)
                                    └── tool_use (工具调用)
```

### RAG 流程

```
load_session → load_knowledge_base → retrieve → rerank → evaluate_relevance
    → [高相关] generate_answer → citation
    → [低相关] reform_query → [重试/降级] web_search
```

## API 端点

### Chat API
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/chat | 发送消息（支持SSE流式） |
| POST | /api/v1/chat/sessions | 创建会话 |
| GET | /api/v1/chat/sessions | 列出会话 |
| GET | /api/v1/chat/sessions/{id}/messages | 获取会话消息 |

### Knowledge Base API
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/knowledge-bases | 创建知识库 |
| GET | /api/v1/knowledge-bases | 列出知识库 |
| POST | /api/v1/ingest/upload | 上传文档（异步入库） |
| GET | /api/v1/documents/{id}/status | 查询入库状态 |
| GET | /api/v1/knowledge-bases/{id}/documents | 列出知识库文档 |

### Health API
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |

## 部署方式

```bash
# 1. 配置环境变量
cp .env.example .env

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f app
```

## 环境变量

关键配置项：
- `DATABASE_URL`：PostgreSQL 连接串
- `REDIS_URL`：Redis 连接串
- `MILVUS_HOST`/`MILVUS_PORT`：Milvus 地址
- `MINIO_ENDPOINT`/`MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`：MinIO 配置
- `LLM__API_KEY`：GLM API密钥
- `WEB_SEARCH__API_KEY`：Tavily 搜索API密钥

# QT-Agent 开发 TODO

> 基于《从0开始手搓智能体》整理，覆盖主图、RAG、多模态入库、上下文持久化、Skill、MCP、缓存、日志与 Docker 部署。 

## 使用说明
- [ ] 按阶段推进，建议先完成 P0-P8 形成可用闭环，再扩展 Skill / MCP / 并发优化。
- [ ] 每完成一个任务，补充对应的 PR / commit / 设计说明链接。
- [ ] 每个阶段结束后，执行该阶段验收项。

---

## P0 项目初始化与工程骨架

### 目标
建立统一工程底座：目录结构、配置体系、日志、FastAPI 启动入口、Docker 基础设施。

### 任务清单
- [ ] 创建项目目录结构
  - [ ] 创建 `app/api/core/schemas/services/graph/providers/repositories/db/cache/retrieval/memory/ingestion/skills/mcp/utils/tests`
  - [ ] 创建 `docker/scripts/.env.example/requirements.txt/README.md`
  - [ ] 补充 `__init__.py` 与占位文件
- [ ] 建立配置系统
  - [ ] 实现 `Settings(BaseSettings)`
  - [ ] 接入 APP/DB/REDIS/MILVUS/MINIO/LLM/EMBEDDING/STARTUP_RETRY/CACHE/SSE 配置
  - [ ] 提供 `.env.example`
- [ ] 建立基础日志系统
  - [ ] 实现统一 `logger`
  - [ ] 支持 `trace_id/request_id/session_id/user_id` 注入
  - [ ] 定义 access/business/error/audit 日志格式
- [ ] 建立 FastAPI 启动入口
  - [ ] 实现 `app/main.py`
  - [ ] 实现 `app/lifecycle.py`
  - [ ] 挂载总路由 `/api/v1`
  - [ ] 增加健康检查接口 `/health`
- [ ] 建立 Docker 基础设施
  - [ ] 编写 `Dockerfile`
  - [ ] 编写 `docker-compose.yml`
  - [ ] 定义 `app/postgres/redis/milvus/minio` 服务
  - [ ] 加入 startup retry 机制

### 交付物
- [ ] 基础项目骨架
- [ ] `.env.example`
- [ ] `Dockerfile`
- [ ] `docker-compose.yml`
- [ ] FastAPI 可启动服务

### 验收项
- [ ] 项目可本地启动
- [ ] 健康检查接口返回正常
- [ ] 配置可从 `.env` 正确读取
- [ ] 日志可打印 trace 信息

---

## P1 数据层与基础中间件接入

### 目标
接通 PostgreSQL、Redis、Milvus、MinIO，为会话、缓存、向量、文件存储提供底层能力。

### 任务清单
- [ ] PostgreSQL 接入
  - [ ] 创建 async DB engine/session
  - [ ] 定义 `users/sessions/messages/knowledge_bases/documents/audit_logs` 表
  - [ ] 预留 `graph_checkpoints` 表
  - [ ] 配置迁移工具
- [ ] Redis 接入
  - [ ] 实现 `redis_client`
  - [ ] 支持热缓存读写
  - [ ] 支持窗口缓存 key 设计
  - [ ] 预留分布式锁接口
- [ ] Milvus 接入
  - [ ] 实现 vector store 抽象
  - [ ] 实现 `MilvusStore`
  - [ ] 定义 collection schema
  - [ ] 支持 `metadata filter + similarity_search`
- [ ] MinIO 接入
  - [ ] 实现对象上传/下载
  - [ ] 支持 bucket 初始化
  - [ ] 保存原始文件与中间产物

### 交付物
- [ ] DB models + migrations
- [ ] Redis client
- [ ] Milvus store
- [ ] MinIO client

### 验收项
- [ ] PostgreSQL 可建表并读写
- [ ] Redis 可缓存窗口消息
- [ ] Milvus 可写入和检索向量
- [ ] MinIO 可上传下载文件

---

## P2 统一抽象层与 Provider 工厂

### 目标
建立统一的 LLM、Embedding、VectorStore、Search、Parser、Skill 抽象接口，隔离供应商 SDK。

### 任务清单
- [ ] LLM 抽象层
  - [ ] 定义 `BaseLLMProvider.chat`
  - [ ] 定义 `BaseLLMProvider.stream_chat`
  - [ ] 定义 `LLMResponse / LLMStreamChunk` 统一返回结构
  - [ ] 实现 `LLMProviderFactory`
- [ ] 接入 `glm-4-flash` Provider
  - [ ] 实现 `GLMProvider.chat`
  - [ ] 实现 `GLMProvider.stream_chat`
  - [ ] 支持 `model` 参数路由
- [ ] Embedding 抽象层
  - [ ] 定义 `BaseEmbeddingProvider`
  - [ ] 实现默认 embedding provider
- [ ] Search / Parser / VectorStore / Skill 抽象
  - [ ] 定义 `BaseSearchProvider`
  - [ ] 定义 `BaseParser`
  - [ ] 对接 `BaseVectorStore`
  - [ ] 定义 `BaseSkill`

### 交付物
- [ ] providers/base interfaces
- [ ] glm provider
- [ ] embedding provider
- [ ] factory 模式

### 验收项
- [ ] 业务层只依赖抽象接口
- [ ] 可通过配置切换默认模型
- [ ] `stream_chat` 输出统一格式

---

## P3 Chat API 与 SSE 流式输出闭环

### 目标
打通最小可用聊天主链路：请求进入、调用 LLM、SSE 返回、消息落库。

### 任务清单
- [ ] 定义 Chat 请求/响应 Schema
  - [ ] 定义 `ChatRequest(user_id, username, session_id, message, model, stream)`
  - [ ] 定义历史消息查询 schema
- [ ] 实现 `ChatService`
  - [ ] 加载会话
  - [ ] 调用 `provider.chat / stream_chat`
  - [ ] 支持 SSE 包装
  - [ ] 持久化消息
- [ ] 实现 `/api/v1/chat`
  - [ ] 支持 `stream=true`
  - [ ] 支持非流式 fallback
  - [ ] 支持 `session_id`
- [ ] 实现 `/api/v1/chat/history`
  - [ ] 按 `session_id` 返回历史消息

### 交付物
- [ ] chat API
- [ ] SSE 流式输出
- [ ] 消息表持久化

### 验收项
- [ ] 前端可实时收到 delta
- [ ] 聊天结束后消息可查询
- [ ] `session_id` 可关联多轮对话

---

## P4 LangGraph 主图骨架

### 目标
建立主图执行框架，打通 `init/load_context/cache_check/supervisor_route/post_process/persist_state` 主流程。

### 任务清单
- [ ] 定义 `GraphState`
  - [ ] 包含 `trace_id/request_id/session_id/user_id/username`
  - [ ] 包含 `user_message/normalized_query/model/stream`
  - [ ] 包含 `route_type/recall_count/top_k/retrieved_docs/relevance_score`
  - [ ] 包含 `cache_hit/cache_context/need_web_fallback/response_text`
- [ ] 实现图节点
  - [ ] `init_request`
  - [ ] `load_session_context`
  - [ ] `check_window_cache`
  - [ ] `post_process`
  - [ ] `persist_state`
- [ ] 实现 `supervisor_route`
  - [ ] 规则优先路由
  - [ ] LLM 分类补充
  - [ ] 当前支持 `smalltalk/knowledge_qa/web_search`
  - [ ] 预留 `skill` 路由入口
- [ ] 编译 `graph builder`
  - [ ] 完成 `START -> ... -> END` 主图
  - [ ] 让 `ChatService` 通过 graph 调用

### 交付物
- [ ] LangGraph 主图
- [ ] Supervisor 路由器
- [ ] GraphState 模型

### 验收项
- [ ] 请求可经由图执行
- [ ] `route_type` 决策可追踪
- [ ] 主图可插接子图

---

## P5 RAG 检索闭环

### 目标
完成知识库问答路径：query 处理、向量召回、重排、相关性判断、循环 recall、回答生成。

### 任务清单
- [ ] 实现检索模块
  - [ ] 实现 `retriever`
  - [ ] 支持 `top-k`
  - [ ] 支持 `metadata filter`
  - [ ] 按用户可见范围过滤
- [ ] 实现 RAG 子图节点
  - [ ] `rag_prepare`
  - [ ] `recall_documents`
  - [ ] `rerank_documents`
  - [ ] `evaluate_relevance`
  - [ ] `reform_query`
  - [ ] `answer_by_rag`
  - [ ] `fallback_to_websearch`
- [ ] 实现 recall 循环
  - [ ] 支持 `max_recall_count`
  - [ ] 默认 2 次
  - [ ] 支持手动调整
- [ ] 实现 RAG Answer Prompt
  - [ ] 组装 citation context
  - [ ] 将检索结果喂给 LLM 总结
- [ ] 将 RAG 子图接入主图
  - [ ] `supervisor_route -> rag_subgraph`
  - [ ] 结果回写 `state.response_text`

### 交付物
- [ ] retrieval 模块
- [ ] RAG 子图
- [ ] query rewrite / relevance check

### 验收项
- [ ] 知识库问题可命中 Milvus 返回答案
- [ ] 低命中时可自动重试 recall
- [ ] 过程日志可看到 `score` 与 `recall_count`

---

## P6 多模态知识入库

### 目标
支持文本、PDF、图片上传入库，完成解析、清洗、切块、embedding、Milvus 写入、元数据落库。

### 任务清单
- [x] 上传接口与文件存储
  - [x] 实现 `/api/v1/ingest/upload`
  - [x] 将原文件保存到 MinIO
  - [x] 记录 `documents` 元数据
- [x] Parser 实现
  - [x] `TextParser`
  - [x] `PDFParser`
  - [x] `ImageParser`
  - [x] 扫描型 PDF OCR fallback
- [x] Chunk 与 Metadata
  - [x] 实现 `chunker`
  - [x] 构建 `doc_id/page/chunk_index/kb_id/owner_user_id/source_type` 等 metadata
- [x] Embedding 与向量入库
  - [x] 对 chunk 批量 embedding
  - [x] 写入 Milvus
  - [x] 更新 `chunk_count / parse_status`
- [x] 入库异步化
  - [x] 文件解析 async 化
  - [x] 高耗时 OCR/embedding 预留线程池或任务分发接口

### 交付物
- [x] ingest API
- [x] parser/chunker/ocr pipeline
- [x] Milvus 入库闭环

### 验收项
- [x] `txt/md/pdf/image` 可成功入库
- [x] `documents` 表可查看状态
- [x] 入库后可立即参与检索

---

## P7 WebSearch 降级路径

### 目标
当知识库匹配度持续偏低时，自动降级到联网搜索，并明确提示用户回答来源。

### 任务清单
- [x] Search Provider 抽象实现
  - [x] 实现 `BaseSearchProvider`
  - [x] 实现 websearch provider
- [x] 构建 WebSearch 子图
  - [x] `web_prepare`
  - [x] `web_search`
  - [x] `result_clean`
  - [x] `answer_by_web`
- [x] 降级提示
  - [x] 当 `need_web_fallback=true` 时追加固定提示
  - [x] 声明"当前知识库无相关内容，以下为网络搜索整理"
- [x] 接入主图
  - [x] RAG relevance 低时跳转 `websearch_subgraph`
  - [x] supervisor 也支持直接 `web_search` 路由

### 交付物
- [x] websearch provider
- [x] websearch 子图
- [x] RAG -> WebSearch fallback

### 验收项
- [x] 知识库低命中时可自动走联网搜索
- [x] 回答前有清晰降级提示
- [x] 搜索结果经清洗后进入 LLM

---

## P8 上下文管理、Checkpointer 与 Cache-Hit

### 目标
完成 Redis 热窗口、PostgreSQL 历史持久化、LangGraph checkpointer 以及相似问题缓存命中增强。

### 任务清单
- [x] Session 历史恢复
  - [x] 实现 `history_loader`
  - [x] 先查 Redis 热窗口
  - [x] 未命中查 PostgreSQL 历史
- [x] LangGraph Checkpointer
  - [x] 接入 PostgreSQL checkpointer
  - [x] 支持根据 `session_id` 恢复图状态
- [x] 窗口缓存命中
  - [x] 实现 `WindowCacheService.hit`
  - [x] 相似问题直接复用或增强上下文
  - [x] 阈值配置化
- [x] 摘要记忆
  - [x] 长历史压缩为 summary
  - [x] 保留原始历史 + 摘要 + 短期窗口三层记忆

### 交付物
- [x] session memory 模块
- [x] checkpointer
- [x] window cache
- [x] summary memory

### 验收项
- [x] `session_id` 可恢复历史对话
- [x] 缓存命中结果可进入当前回答上下文
- [x] 上下文过长时能压缩摘要

---

## P9 用户管理与知识库权限隔离

### 目标
先实现 `user_id/username` 维度隔离，再为 `token/tenant/accessible_kb_ids` 预留扩展能力。

### 任务清单
- [ ] 用户接口
  - [ ] 实现 `/api/v1/users`
  - [ ] 实现 `/api/v1/users/{user_id}`
- [ ] 知识库接口
  - [ ] 实现创建知识库接口
  - [ ] 实现文档管理接口
  - [ ] 实现知识检索调试接口
- [ ] 权限过滤
  - [ ] 检索前按 `owner_user_id` 过滤
  - [ ] 预留 `tenant_id/accessibile_kb_ids` 策略
  - [ ] 权限控制放在检索层，不只 API 层

### 交付物
- [ ] users API
- [ ] knowledge API
- [ ] retrieval 权限过滤

### 验收项
- [ ] 不同用户默认只能检索自己的知识范围
- [ ] 后续可平滑升级 token/tenant 模型

---

## P10 Skill 模块化与 Supervisor 扩展

### 目标
实现像搭积木一样的 Skill 接入机制，使未来报表分析、政策对比等能力可插拔。

### 任务清单
- [ ] Skill 基础抽象
  - [ ] 定义 `BaseSkill(name, description, can_handle, invoke)`
  - [ ] 定义 skill schema
- [ ] Skill Registry
  - [ ] 实现 `register/get/list`
  - [ ] 支持启动时自动注册
- [ ] Skill Router Node
  - [ ] 在主图中新增 `skill_router_subgraph`
  - [ ] 支持 future skills 占位
- [ ] 示例 Skill
  - [ ] 提供 `knowledge_qa skill` 封装
  - [ ] 提供 `web_search skill` 封装
  - [ ] 预留 `report_analysis / policy_compare skill` 目录

### 交付物
- [ ] `skills/base.py`
- [ ] `skills/registry.py`
- [ ] `skill_router_subgraph`

### 验收项
- [ ] 新增 skill 时无需改核心 chat service
- [ ] supervisor 可识别并路由 skill 类型请求

---

## P11 MCP 桥接层

### 目标
让系统具备 MCP 兼容扩展能力，支持未来接入外部工具与内部系统能力。

### 任务清单
- [ ] MCP 客户端与注册
  - [ ] 实现 `mcp/client.py`
  - [ ] 实现 `mcp/registry.py`
- [ ] MCP Tool Adapter
  - [ ] 定义 base adapter
  - [ ] 实现 `tool_adapter`
- [ ] Skill/MCP 协同
  - [ ] 允许 skill 内调用 MCP tool
  - [ ] 为 supervisor 预留 `mcp_call` 路由

### 交付物
- [ ] MCP bridge
- [ ] tool adapter

### 验收项
- [ ] MCP 调用能力与业务解耦
- [ ] 后续新工具可通过桥接层接入

---

## P12 异步并发优化与稳定性加固

### 目标
对高频 I/O、长耗时任务、流式输出、锁与超时控制进行系统性优化。

### 任务清单
- [ ] I/O 全 async 化
  - [ ] PostgreSQL async
  - [ ] Redis async
  - [ ] Milvus async 封装
  - [ ] MinIO async 调用方式或线程池包装
  - [ ] WebSearch async
- [ ] 并发控制
  - [ ] 加入 Semaphore 控制 embedding 并发
  - [ ] 加入 Redis 分布式锁避免重复入库
  - [ ] 加入 provider 调用超时
- [ ] 长任务接口
  - [ ] 预留 `BackgroundTaskDispatcher`
  - [ ] 为 OCR/批量 embedding/归档预留任务队列迁移口
- [ ] 失败降级策略
  - [ ] RAG -> WebSearch
  - [ ] 指定模型失败 -> 默认模型
  - [ ] Redis 不可用 -> 关闭缓存仍可回答
  - [ ] MinIO 不可用 -> 禁止上传但问答可用

### 交付物
- [ ] 异步化服务
- [ ] 限流/锁/超时策略
- [ ] 降级机制

### 验收项
- [ ] 高并发场景无明显阻塞
- [ ] 单个中间件故障不致全局不可用

---

## P13 可观测性、审计与测试

### 目标
建立节点级日志、审计表、链路追踪和测试体系，保证问题可定位、功能可验收。

### 任务清单
- [ ] 图节点日志
  - [ ] 记录 `load_context/cache_hit/supervisor/recall/rerank/relevance/websearch/llm/sse` 事件
  - [ ] 输出 `latency/status/extra`
- [ ] 审计日志
  - [ ] 重要行为写 `audit_logs`
  - [ ] 记录 `route_type/source_type/fallback reason`
- [ ] 测试体系
  - [ ] 编写 unit tests
  - [ ] 编写 integration tests
  - [ ] 编写 e2e tests
- [ ] 验收用例
  - [ ] 知识库高命中回答
  - [ ] 知识库低命中自动 websearch
  - [ ] session 恢复
  - [ ] cache-hit 增强
  - [ ] 多模态入库
  - [ ] skill 注册生效

### 交付物
- [ ] 测试套件
- [ ] 日志追踪规范
- [ ] 验收清单

### 验收项
- [ ] 关键流程均有自动化测试
- [ ] 错误可定位到具体节点
- [ ] 审计表可追溯主要行为

---

## P14 发布准备与文档交付

### 目标
完成部署说明、初始化脚本、演示数据、运维文档，达到可交付状态。

### 任务清单
- [ ] 初始化脚本
  - [ ] `scripts/init_db.py`
  - [ ] `scripts/init_milvus.py`
  - [ ] `scripts/seed_demo_data.py`
- [ ] README 与运维文档
  - [ ] 本地启动说明
  - [ ] Docker 启动说明
  - [ ] 环境变量说明
  - [ ] 接口说明
  - [ ] 常见故障排查
- [ ] 发布检查
  - [ ] 镜像可构建
  - [ ] `docker-compose` 可启动
  - [ ] 数据库迁移脚本可执行
  - [ ] 默认模型与检索链路可运行

### 交付物
- [ ] README
- [ ] init scripts
- [ ] 可启动部署包

### 验收项
- [ ] 新环境可按文档完成部署
- [ ] 演示数据可跑通完整闭环

---

## 里程碑
- [ ] M1 最小可用聊天闭环（P0-P3）
- [ ] M2 知识库问答闭环（M1 + P4-P6）
- [ ] M3 企业级可用版本（M2 + P7-P11）
- [ ] M4 稳定发布版本（M3 + P12-P14）

## 最终完成定义（Definition of Done）
- [ ] 主图支持 `smalltalk / knowledge_qa / web_search / skill reserved`
- [ ] RAG 支持 `top-k、re-recall、relevance check、fallback`
- [ ] 支持 `txt/pdf/image` 入库
- [ ] 支持 `session_id` 恢复对话
- [ ] 支持 SSE 流式输出
- [ ] 支持统一 LLM provider 抽象
- [ ] 支持 cache-hit
- [ ] 支持日志追踪
- [ ] 支持 Docker 部署
- [ ] 为 MCP 和 Skill 扩展预留清晰接口

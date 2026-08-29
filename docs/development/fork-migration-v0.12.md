# Fork 架构与 v0.12.0 迁移说明

## 1. 基线结论

- fork 的 `dev`：`f467312`
- 官方 `main`：`9ad3e4e4`，标签 `v0.12.0`
- 共同祖先：`37cdc28c`，标签 `v0.11.0`
- 共同祖先之后：fork 86 个提交，官方 4 个提交
- fork 的累计差异包含 601 个文件和约 332 万行新增内容；绝大部分来自
  PDF.js 解压目录、NLTK/Tiktoken 数据、压测结果和备份文件，并非业务代码
- 对最终目录树做三方合并时有 11 个冲突文件，集中在模型管理、文件加载、
  聊天、设置和 Agent/MCP 接入点

因此，本次采用“官方 `v0.12.0` 为基线，净迁移 fork 功能”的方式，在
`codex/migrate-dev-to-v0.12` 分支实施；原 `dev` 不改写，继续作为回退基线。

## 2. 逻辑架构

### 2.1 分层

| 层 | 主要位置 | 职责 |
| --- | --- | --- |
| 启动与配置 | `app.py`、`flowsettings.py` | 读取环境变量，声明模型、索引和功能开关，启动 Gradio |
| 应用编排 | `libs/ktem/ktem/app.py`、`main.py` | 注册推理与索引插件，创建全局状态，组织页面和登录后的权限可见性 |
| UI 与会话 | `libs/ktem/ktem/pages/` | 聊天、登录、设置、资源管理、实时语音入口及 Gradio 事件链 |
| 索引应用层 | `libs/ktem/ktem/index/` | 索引实例管理、文件/分组 UI、索引与检索管线装配 |
| RAG/Agent 编排 | `libs/ktem/ktem/reasoning/` | Simple/Decompose QA、ReAct、ReWOO，组装检索器、LLM 与工具 |
| 核心组件库 | `libs/kotaemon/kotaemon/` | Loader、Splitter、Embedding、Vector/Doc Store、Reranker、Citation QA、Agent/MCP |
| 元数据与配置持久化 | `libs/ktem/ktem/db/` 及各类 `manager.py` | SQLModel 元数据、用户/会话/设置、模型配置及索引配置 |
| 辅助服务与运维 | `services/`、`run.sh`、Dockerfile | 本地重排、模型连通性检查、进程和容器启动 |

`kotaemon` 是可复用的 RAG 核心库，`ktem` 是带数据库、权限和 Gradio UI 的
应用层。fork 的业务定制应优先留在 `flowsettings.py` 和 `ktem`，避免直接修改
`kotaemon` 核心；这样以后吸收上游版本时冲突面更小。

### 2.2 启动链路

1. `app.py` 触发 TheFlow 加载 `flowsettings.py`。
2. `ktem.main.App` 初始化 `BaseApp`。
3. `BaseApp.register_reasonings()` 根据 `KH_REASONINGS` 动态加载推理管线。
4. `IndexManager.on_application_startup()` 从配置/数据库创建索引实例。
5. `App.ui()` 创建聊天、文件、资源、设置和帮助页面，聊天输入区内注册 ASR 入口。
6. 各页面先声明公共事件，再订阅事件并注册 Gradio 回调。
7. 登录事件根据管理员角色切换资源管理、文件管理和快速上传的可见性。

### 2.3 文档入库链路

```text
FileIndexPage 上传
  -> FileIndex 的 indexing pipeline
  -> IndexDocumentPipeline 选择 reader_mode
  -> Kotaemon Loader（默认/Adobe/Azure/Docling/PaddleOCR）
  -> 文档切分与元数据提取
  -> Embedding
  -> DocStore + VectorStore + SQL 关系元数据
  -> onFileIndexChanged 刷新文件、分组和聊天选择器
```

官方 `v0.12.0` 新增的 PaddleOCR reader 被完整保留。fork 默认只在 UI 暴露
`default` loader；可通过 `KH_FILE_LOADER_MODES` 逐项打开其他 loader，而不是
在源码里注释官方实现。

### 2.4 问答链路

```text
ChatPage.submit_msg
  -> 解析 @文件/@分组/可选 WebSearch 与 URL
  -> FileSelector 生成选中文档 ID
  -> FileIndex 构造向量/关键词检索器
  -> FullQAPipeline 或 FullDecomposeQAPipeline
  -> 检索、重排、Citation QA/流式生成
  -> Render 生成答案、引用、图表/思维导图
  -> Conversation + Settings + 检索历史持久化
```

共享知识库模式下，普通用户可以检索管理员维护的文件和分组，但不能进入文件
管理页或使用快速上传。关闭 `KH_SHARED_FILE_COLLECTION` 后恢复官方的按用户
隔离查询。

### 2.5 Agent 与 MCP

官方 `v0.12.0` 的 MCP Manager、MCP 资源页和 ReAct/ReWOO 动态工具加载均保留。
医疗部署默认只启用 Simple/Decompose QA；设置 `KH_ENABLE_AGENT_REASONINGS=true`
后才注册 Agent。Agent 默认只提供内部文档与 LLM 工具，
`KH_ENABLE_EXTERNAL_AGENT_TOOLS=true` 后再开放 Wikipedia/Google，MCP 工具不受
该开关影响。

### 2.6 模型调用架构

| 类别 | 当前默认模型 | 应用组件 | API |
| --- | --- | --- | --- |
| LLM/VLM | `qwen3-vl-flash` | `ChatOpenAI` | `POST /api/v1/chat/completions` |
| Embedding | `qwen3-vl-embedding` | `GeekAIEmbeddings` | `POST /api/v1/embeddings` |
| Rerank | `qwen3-rerank` | `GeekAIReranking` | `POST /api/v1/rerank` |
| ASR | Mock 多说话人流 | `MockASRProvider` | 远端 API 待接入 |

`flowsettings.py` 从本地 `.env` 读取配置，三个模型 Manager 将配置注册到应用
数据库；索引入库调用默认 Embedding，问答检索后调用默认 Reranker，最终由默认
LLM 生成答案。GeekAI 属于环境变量托管的配置，API Key 或模型名变更后会在
下次启动时同步到应用数据库。`KH_MODEL_PROFILE=lmstudio` 可恢复迁移前的本地
三模型组合，设为 `official` 则使用上游默认配置。

## 3. 两种升级方案对比

### 3.1 将 `dev` rebase 到官方 `main`

优点：

- 表面上形成线性历史，所有本地提交仍可逐个追溯
- 如果本地提交少、职责单一且测试完整，后续 `git bisect` 体验较好

缺点：

- 需要重放 86 个粒度不稳定的提交，许多提交名仅为 `update`
- 同一文件的中文化和配置修改会在 rebase 中重复触发冲突
- 会原样保留备份、缓存、压测输出和解压第三方资产造成的历史膨胀
- 改写已经发布的 `dev` 历史，团队成员需要强制同步
- 旧提交会先删除/注释官方能力，再由人工在后续提交里恢复，验证成本高

### 3.2 在官方 `main` 上迁移 fork 功能

优点：

- 官方 MCP、PaddleOCR、uv 和安全修复天然作为基线，不会被旧文件整体覆盖
- 可以按业务能力形成少量可审查变更，并把配置差异改成环境开关
- 可以排除生成物、明文凭据、绝对路径和历史备份
- 原 `dev` 保持不变，回退和逐项对照简单
- 后续升级只需合并新的上游增量，长期冲突面更小

缺点：

- 需要一次性识别哪些差异是业务需求，哪些只是历史现场
- 原来的 86 个提交不会出现在新分支第一父历史中，需要通过本文档和 `dev`
  分支追溯
- 对未覆盖的边缘部署方式，需要在验收阶段补充测试

本项目的本地提交数量、生成物体积和横切式中文化都明显偏向第二种方案。

## 4. 本次迁移范围

### 保留并适配

- 医疗中文品牌、中文界面和中文会话命名提示
- 管理员维护、普通用户检索的共享知识库权限模型
- 文件分组全选、分组优先、取消检索选择、快速上传后不自动提交问题
- 旧用户设置与新默认设置的合并，避免新增设置键导致 `KeyError`
- 引用生成超时调整和思维导图相关设置
- GeekAI LLM、专用 Embedding/Rerank 协议适配器，以及可选的 LM Studio/本地
  TEI-style 模型配置
- 聊天输入框实时语音入口、多说话人转写面板和管理员声纹库
- 压测源码、模型连通性工具和定制 Docker 入口
- 医疗 favicon 和帮助内容

### 以官方实现为准

- uv workspace 和 `uv.lock`
- MCP Server 管理、模型/索引重命名及对应数据库 Manager
- PaddleOCR PPStructureV3/PaddleOCR-VL loader
- `@WebSearch`/文件 mention 的新版解析与显示逻辑
- Cohere `rerank-v4.0-fast` 默认配置

### 不迁移

- `nltk_data/`、`tiktoken_cache/`
- PDF.js 解压目录及 ZIP 二进制；继续使用官方构建脚本下载
- 压测结果 CSV 和历史 `code_bak/`
- `flowsettings.bak.py`、按日期命名的 Python 备份
- 从旧环境导出的 `requirements*.txt`；依赖以 `pyproject.toml + uv.lock` 为准
- 源码中注释掉的真实 API Key、机器绝对路径和旧版 Dockerfile

## 5. 关键配置

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `KH_MODEL_PROFILE` | `geekai` | 模型配置集：`geekai`、`lmstudio` 或 `official` |
| `GEEKAI_API_BASE_URL` | `https://geekai.co/api/v1` | GeekAI OpenAI-compatible API 根地址 |
| `GEEKAI_API_KEY` | 占位值 | GeekAI API Key，仅放在本地 `.env` |
| `GEEKAI_CHAT_MODEL` | `qwen3-vl-flash` | 默认 LLM/VLM |
| `GEEKAI_EMBEDDING_MODEL` | `qwen3-vl-embedding` | 默认 Embedding，调用 `/embeddings` |
| `GEEKAI_RERANK_MODEL` | `qwen3-rerank` | 默认 Reranker，调用 `/rerank` |
| `KH_SHARED_FILE_COLLECTION` | `true` | 普通用户可检索管理员维护的共享资料 |
| `KH_FILE_LOADER_MODES` | `default` | UI 可选 loader，逗号分隔，可加入 Paddle/Docling 等 |
| `KH_ENABLE_URL_UPLOAD` | `false` | 是否显示 URL 入库入口 |
| `KH_WEB_SEARCH_COMMAND` | 空 | Web 搜索 mention 名；设为 `WebSearch` 即启用入口 |
| `KH_ENABLE_AGENT_REASONINGS` | `false` | 是否注册 ReAct/ReWOO |
| `KH_ENABLE_EXTERNAL_AGENT_TOOLS` | `false` | 是否开放 Wikipedia/Google |
| `KH_ENABLE_ASR` | `true` | 是否在聊天输入框启用实时语音入口 |
| `KH_ASR_PROVIDER` | `mock` | ASR Provider；远端 API 接通前使用模拟流 |
| `KH_START_LOCAL_RERANK` | `false` | `run.sh` 是否同时启动本地重排服务 |

GeekAI 的 LLM 接口兼容 OpenAI Chat Completions，直接复用 `ChatOpenAI`。
`qwen3-vl-embedding` 的 `input` 必须是 `[{"type": "text", "text": ...}]`
而不是 OpenAI 的字符串数组，因此使用 `GeekAIEmbeddings` 适配器。GeekAI
Rerank 返回的 `index` 当前代表排序位置而非原文档位置，`GeekAIReranking` 会按
响应中的文档内容安全映射回原始 `Document`，并写入 `reranking_score`。

## 6. 验证结果与边界

- `uv lock --check`：通过，锁文件与 workspace 配置一致
- 迁移涉及的 Python 文件：Ruff 格式及静态检查通过，`compileall` 通过
- 应用构建烟测：启用用户管理与 ASR 时成功创建 443 个 Gradio 组件、267 条
  事件依赖，资源管理包含独立 ASR 与声纹配置页且不再包含 MCP 页签
- macOS Bash 3.2 下执行 `sh run.sh --restart` 后，首页 HTTP 状态为 200；启动
  脚本会跳过缺少项目依赖的 Python 虚拟环境
- `ktem` 本地测试：除上游 `test_qa.py` 引用不存在的顶层 `index` 模块而无法收集
  外，其余 77 个测试通过；聊天、ASR、会话权限、通知、模型隔离和汉化均覆盖
- `kotaemon` 核心测试：115 个通过、20 个按可选依赖跳过、5 个 Milvus
  用例暂不执行；当前旧 `venv` 使用的 `setuptools 84.0.0` 已不提供
  `pkg_resources`，而官方 `uv.lock` 锁定 `setuptools 80.9.0`
- 官方 `ktem_tests/test_qa.py` 引用了仓库中不存在的顶层 `index` 模块，完整
  应用测试集会在收集阶段失败；该问题在未修改的官方 `v0.12.0` 中同样存在
- GeekAI 真实接口验证：Chat Completions 正常生成；Embedding 一次处理两段文本，
  返回两个 2560 维向量；Rerank 能按相关性重排两段文本；LLM 流式输出正常
- GeekAI 协议适配单测覆盖批处理、向量顺序、Rerank 文档映射和异常响应；
  PaddleOCR 可选依赖未安装，因此相关集成用例仍按官方规则跳过
- 压测脚本已通过静态检查和编译检查；当前环境未安装可选的 `locust`，未实际
  发起压力测试

## 7. 后续吸收上游更新

1. 获取官方更新并在临时集成分支合并，不再把整个 fork rebase 到上游。
2. 先运行核心库与应用层单测，再验证入库、共享权限、问答、设置升级和语音页。
3. 冲突时优先保留官方核心实现，把 fork 行为留在显式配置或窄范围 UI 适配中。
4. 禁止提交模型、运行数据、解压第三方包、日志、压测结果或备份文件。

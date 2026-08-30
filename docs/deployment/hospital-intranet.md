# 医院内网部署与运维手册

本文面向医院信息科和实施人员。目标是让构建阶段与运行阶段彻底分离：依赖下载、
镜像构建在可联网且与目标服务器同架构的构建机完成；医院运行机只导入已经校验的
镜像，不执行 `pip`、`uv sync`、模型下载或前端 CDN 请求。

## 1. 运行边界

```text
医生浏览器
    │ HTTP(S)，院内网络
    ▼
Kotaemon 医院应用
    ├── SQLite / 文档库 / 向量库 ──► ktem_app_data（本地持久化）
    ├── LLM / Embedding ───────────► OpenAI-compatible 模型网关
    ├── Rerank ────────────────────► /rerank 兼容接口
    └── ASR（可选）────────────────► 院内 ASR 接口
```

`hospital-external` 是过渡档：只允许白名单中的 HTTPS 模型域名（默认 GeekAI）和
内网地址。`hospital-offline` 是最终档：只允许回环、私网 IP、单标签服务名及
`.local`、`.internal`、`.lan` 地址。应用层策略不能替代防火墙，生产环境仍应在
出口网关只放行明确的模型服务地址。

## 2. 联网构建机制作离线镜像

构建机必须与医院服务器使用相同 CPU 架构。执行：

```bash
docker build -f Dockerfile.hospital -t kotaemon-hospital:0.12 .
docker save kotaemon-hospital:0.12 -o kotaemon-hospital-0.12.tar
sha256sum kotaemon-hospital-0.12.tar > kotaemon-hospital-0.12.tar.sha256
```

将以下文件通过医院批准的介质传入内网：镜像 tar、校验文件、
`docker-compose.hospital.yml`、`.env.hospital.example`、`scripts/` 目录以及本项目
同版本代码包。禁止把真实 `.env`、`ktem_app_data` 或测试病历带出医院。

## 3. 内网服务器一条命令部署

先验证介质并导入镜像：

```bash
sha256sum -c kotaemon-hospital-0.12.tar.sha256
docker load -i kotaemon-hospital-0.12.tar
./scripts/deploy_hospital.sh --prepare
```

编辑 `.env`，至少替换管理员密码和模型密钥。文件权限会被设置为 `600`。然后执行：

```bash
./scripts/deploy_hospital.sh --docker
```

该命令依次运行配置自检、创建/更新容器并显示状态；不会执行镜像拉取。原生 Python
环境已经离线安装好时，可改用 `./scripts/deploy_hospital.sh --native`。

## 4. 模型配置

过渡阶段使用 `.env.hospital.example` 默认的 GeekAI 配置。最终本地化时调整为：

```dotenv
KH_DEPLOYMENT_MODE=hospital-offline
KH_MODEL_PROFILE=lmstudio
KH_LOCAL_MODEL_BASE_URL=http://model-gateway:8000/v1
KH_LOCAL_MODEL_API_KEY=<INTERNAL_KEY>
KH_LOCAL_CHAT_MODEL=qwen3-vl
KH_LOCAL_EMBEDDING_MODEL=qwen3-vl-embedding
KH_LOCAL_RERANK_URL=http://rerank-service:8001/rerank
```

本地网关应提供 `/v1/chat/completions`、`/v1/embeddings` 兼容接口；Rerank 服务提供
项目当前适配的 `/rerank` 接口。切换前先在测试环境核对 Embedding 维度、Rerank
请求字段、最大上下文和超时，不要直接复用旧向量库：Embedding 模型或维度变化时
必须重新索引文档。

ASR 尚未正式接入时保持 `KH_ENABLE_ASR=false`。后续启用时，ASR 地址同样必须满足
当前部署档位的出口规则。

## 5. 日常运维

每次启动或变更配置后先执行：

```bash
./run.sh doctor
./run.sh restart
docker compose -f docker-compose.hospital.yml ps
docker compose -f docker-compose.hospital.yml logs --tail=200 app
```

`run.sh restart` 会先执行静态部署自检，再实际调用默认 LLM、Embedding 和 Rerank；
所有必需检查均通过才会继续启动，ASR 为 Mock 时跳过。首次数据库即使已由模型配置
初始化，只要还没有用户，也必须在 `.env` 设置启动管理员和至少 12 位密码。Docker
镜像使用同一前台入口，因此配置或模型服务失败时容器内应用不会进入可用状态。原生
后台启动还会等待首页返回有效 HTTP 状态后才报告成功，默认超时为 90 秒，可用
`KH_APP_START_TIMEOUT` 调整。

医生页面出现故障编号后，在 `ktem_app_data/logs/app.log` 搜索该编号。日志可能包含
文档解析或模型返回的诊断上下文，应按院内敏感数据制度控制访问和备份保留期。

备份前停止写入，然后整体备份 `ktem_app_data`：

```bash
docker compose -f docker-compose.hospital.yml stop app
tar -czf ktem-app-data-backup.tar.gz ktem_app_data
docker compose -f docker-compose.hospital.yml start app
```

升级时先备份数据并保留旧镜像，只修改 `.env` 中的 `KH_HOSPITAL_IMAGE` 标签后重新
执行部署命令。若健康检查失败，恢复旧标签并重新启动；数据库或索引结构发生迁移时
必须先在脱敏副本验证回滚方案。

## 6. 上线检查清单

- `.env` 权限为 `600`，没有默认密码、占位密钥或无关公共 Provider 密钥。
- 防火墙只允许用户入口和配置的模型网关；服务器不具备通用互联网出口。
- `./run.sh doctor` 为零失败，容器健康状态正常。
- 启动日志中 LLM、Embedding、Rerank 均为 `[PASS]`，Mock ASR 为 `[SKIP]`。
- 使用脱敏 PDF、DOCX、XLSX 分别完成上传、索引、问答和证据定位测试。
- 使用无效模型密钥和停机模型服务验证页面中文提示、故障编号和日志关联。
- 验证普通医生看不到模型、索引、用户和声纹等管理员功能。
- 明确数据备份、日志保留、管理员交接和应急回滚责任人。

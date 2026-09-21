# Zeabur 部署：研报知识库工作台

本服务必须作为 **新的独立服务** 创建，不能替换现有 `wire-mesh-agent` 服务。

## 服务来源

- Repository: `mollywangmo-bit/wire-mesh-agent`
- Branch: `feature/report-knowledge-workbench`
- Build type: Dockerfile
- Dockerfile path: `Dockerfile.knowledge-workbench`
- Port: `8080`

## 持久化卷

挂载一个卷到 `/data`。数据库与研报归档必须放在该卷中，避免每次部署后丢失：

```text
WIRE_MESH_KB_DB=/data/knowledge-workbench/knowledge.db
WIRE_MESH_KB_ARCHIVE=/data/wire-mesh-reports
WIRE_MESH_KB_ADMIN_TOKEN=<创建一个新的随机长令牌>
WIRE_MESH_KB_AUTH_USERNAME=<团队登录账号>
WIRE_MESH_KB_AUTH_PASSWORD=<团队登录密码>
WIRE_MESH_KB_SESSION_SECRET=<创建一个新的随机长令牌>
```

首次启动后，把已有 `.md` 报告上传或同步到 `/data/wire-mesh-reports`，再对工作台域名调用 `POST /api/import`。请求头为：

```text
Authorization: Bearer <WIRE_MESH_KB_ADMIN_TOKEN>
```

也可通过 `POST /api/import/report` 以 `{ "filename": "...md", "content": "..." }` 写入单篇报告；该接口同样只接受管理令牌。

## 运行边界

- 该服务不运行 APScheduler，不发送邮件，也不调用原 Agent 的运行接口。
- 新服务故障不会改变现有行研 Agent 的推送节奏。
- 未配置三项 `WIRE_MESH_KB_AUTH_*` 登录变量时，除健康检查外的访问会被拒绝。
- 后续如要自动同步报告，另建一个可重试的归档任务，不放进主 Agent 的关键投递路径。

# 研报知识库工作台（独立子任务）

这是 Wire Mesh Agent 的下游知识库服务。它不修改或调用现有的周报/月报调度、采集、分析和投递流程。

## 本地运行

```bash
python -m knowledge_workbench.import_reports /path/to/report-archive
uvicorn knowledge_workbench.app:app --host 0.0.0.0 --port 8090
```

默认数据库为 `knowledge_workbench/knowledge.db`。部署时请设置：

```text
WIRE_MESH_KB_DB=/persistent-volume/knowledge.db
WIRE_MESH_KB_ARCHIVE=/persistent-volume/report-archive
WIRE_MESH_KB_ADMIN_TOKEN=replace-with-a-secret-token
WIRE_MESH_KB_AUTH_USERNAME=team-user
WIRE_MESH_KB_AUTH_PASSWORD=replace-with-a-strong-password
WIRE_MESH_KB_SESSION_SECRET=replace-with-a-long-random-secret
```

使用 `POST /api/import` 扫描归档目录。若设置了管理令牌，请添加：

```text
Authorization: Bearer <WIRE_MESH_KB_ADMIN_TOKEN>
```

趋势只代表研报文本的提及热度；不是价格、出口等外部市场数据的实时统计。

## Zeabur

使用仓库根目录的 `Dockerfile.knowledge-workbench` 创建新的独立服务。完整配置见 `docs/deployment/zeabur-knowledge-workbench.md`。

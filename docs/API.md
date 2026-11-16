# Local API / 本机接口

FastAPI 只负责 HTTP、上传、有限结果缓存和报告响应；扫描复用核心。正式入口为根目录 start.ps1，默认 127.0.0.1:8080。API-only 保留 python -m workflow_doctor.api --port 8000，根路径 404 属于该独立入口的正常行为，/docs 为离线 Swagger。

| 方法与路径 | 行为 |
| --- | --- |
| GET /health | status=ok，mode=synchronous |
| POST /api/v1/scans | multipart/form-data，重复 files 字段；多个 JSON 或一个 ZIP |
| GET /api/v1/scans/{scan_id} | 取得仍在 TTL/容量范围内的结果 |
| GET /api/v1/scans/{scan_id}/report?format= | text/json/markdown/html，安全附件名、正确 MIME 和字符编码 |
| GET /docs | 本机 Swagger；不加载 CDN |

扫描同步完成才返回 completed，不返回虚构 pending/running。存在风险是成功扫描，HTTP 200，风险状态位于诊断记录；不是仅因风险就返回 500。

## 摘要与统计

响应包括 scan_id/status、file_count/workflow_count/node_count、finding_count/structural_finding_count、findings/dependencies、report_formats、created_at/expires_at。

兼容字段 finding_count 是全部规范化检查数，structural_finding_count 只计结构发现。新增 diagnostic_records 对定位/维度字段进行 Pydantic 校验；diagnostics.statistics 与 JSON 报告 analysis.diagnostics.statistics 同源。

新 check_count 包含通过与不适用；新 finding_count 只计 blocked/risk/unknown；triggered_rule_count 按这些问题的唯一 Rule ID 计数。内部节点/连线、跨工作流图节点/边、静态未解析引用/目标及动态引用分开，不直接比较新旧不同单位。完整契约见 [报告说明](REPORT_FORMAT.md)。

## 错误

统一 {"error":{"code":"固定错误码","message":"脱敏文字"}}。400 表示无效请求/损坏或不安全 ZIP；404 表示未找到、过期、淘汰或重启丢失；413 为请求/文件/数量/结果超限；415 为不支持类型；422 为参数错误；503 为当前操作繁忙；500 为脱敏内部错误。JSON 语法问题通常是 WF001 诊断记录，不是 HTTP 上传失败。

客户端不得通过参数提高服务限制，不自动重试扫描 POST。超时并不代表后台已取消。结果缓存最多 8 份、总预算 32 MiB、约 900 秒 TTL；无持久化，重启清空。保留上传前字节/期限限制与完整 multipart 校验/清理。

服务无认证，不对公网开放。固定本地 CORS 不等于身份认证；原生同源入口没有开发 CORS 例外。用户名、工作流名、节点名、凭证元数据和参数默认脱敏，API 原文件名只保留上传别名。

# Windows 原生部署

需要 Python 3.12（含 py 启动器）与 Node 24.19+ 的 24.x。Node 仅用于准备/构建；运行使用 Python + 已编译前端，无需 Docker、WSL 或 Linux。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Prepare
```

脚本优先 .venv，其次 .venv-312；不存在时用 py -3.12 创建 .venv。自定义解释器应先创建虚拟环境，再传 -PythonPath。-Prepare 安装 deploy/backend/requirements.lock、build.lock，安装项目、npm ci 和同源生产构建。首次需要包网络；运行时不下载用户工作流资源。

默认 http://127.0.0.1:8080，/docs 为 Swagger，/health 为健康端点。短脚本受策略限制时，使用上面的 powershell.exe 形式；它只改变该子进程执行策略，不修改系统设置。

```powershell
.\start.ps1
.\status.ps1
.\stop.ps1
.\start.ps1 -Port 8081
```

脚本无需管理员运行，不修改防火墙、系统服务或已有应用。关闭启动终端不等于停止后台。单项目一个实例；重复启动返回 ALREADY_RUNNING。状态记录仅含 PID/端口/实例标识和锁，位于忽略的 .runtime，不含工作流。

停止采用协作请求，等待约 25 秒，超时报告失败且不强杀。缓存会在重启后丢失，请先下载脱敏报告。更新时先 stop，再取得审查过的源码，运行 start -Prepare；服务运行中不要改写 dist。

## 排错

| 情况 | 处理 |
| --- | --- |
| Python 环境缺失/版本错误 | 安装 Python 3.12 或提供其虚拟环境 -PythonPath；不要用系统旧解释器 |
| Node/npm 缺失 | 安装受支持 Node 24.x，再准备前端 |
| PORT_IN_USE | 选择 -Port；不终止陌生进程 |
| BUILD_MISSING/启动失败 | 停止后重新 -Prepare，确认生产同源构建和依赖 |
| 扫描结果 404 | 可能过期、淘汰或服务重启，重新选择并确认扫描 |
| stop 超时 | 活动扫描可能尚未结束，稍后 status；不强杀 |

API-only 旧入口 python -m workflow_doctor.api --port 8000 保持；5173/8000 为开发模式，不是正式启动方式。已有可选容器配置保留，但未在本地实际构建/启动；不属于原生安装前置条件。

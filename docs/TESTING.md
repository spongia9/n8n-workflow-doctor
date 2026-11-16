# Testing / 测试

完整后端需 Python 3.12，并安装 api/test extras。所有公开输入为合成数据；不得上传真实工作流或凭证。

```text
python -m pip install -e ".[api,test]"
python -m unittest discover -s tests -v
python -m tools.export_frontend_contract --check
python -m tools.review_public_files
python -m tools.review_history
```

frontend 中：

```text
npm ci
npm run typecheck
npm test
npm run build
npm run test:e2e
npx playwright test --config playwright.security.config.ts
npm run build -- --outDir ../.tmp/optimization-dist
npx playwright test --config playwright.optimization.config.ts
```

Windows 可用 npm.cmd / npx.cmd。现有 5173/8000 用户服务活跃时，给普通 E2E 设置 WORKFLOW_DOCTOR_E2E_ISOLATED=1，使用 5175/8001。优化生产套件也使用 5175，顺序运行。真实恶意 HTML 套件使用 5174/8002 的测试服务器，不进入生产镜像。

原生套件先运行 start.ps1，再执行 playwright.native.config.ts；该套件真实停止/重启服务并验证旧扫描 404，不能对用户正在使用的后台执行。可用 WORKFLOW_DOCTOR_NATIVE_TEST_ROOT 与 WORKFLOW_DOCTOR_NATIVE_TEST_PORT 指向隔离测试根和端口。当前 15 项含 14 真接口+1 Mock，17 原生项复用前 14；真实恶意 HTTP 1、优化生产交互 2 分别统计，不冒充唯一数量。

2026-11-16 公开发布副本复验：新建 Python 3.12.13 虚拟环境，按哈希锁安装依赖并安装当前项目，pip check 通过。实际运行后端 313 项、Vitest 55 项、常规浏览器 15 项、原生浏览器 17 项、真实恶意 HTML HTTP 1 项、优化生产交互 2 项，均通过；原生套件复用的 14 项业务断言不重复计作新测试。TypeScript、同源生产构建、实际 OpenAPI 契约通过；npm audit 为 0 漏洞。文件审查针对暂存对象；保留日志在本地，不发布本地路径或原始输入。

远程工作流是否通过，以实际 Actions run 为准。临时 ZIP、报告、trace、日志和原始文件不提交。

2026-11-16 [远程 CI 43830078427](https://github.com/spongia9/n8n-workflow-doctor/actions/runs/43830078427) 对提交 05a3f4c 全部常规任务成功：Windows Python 3.12.10 / Linux Python 3.12.16 分别 313 项后端测试；前端类型、55 项 Vitest、audit 与生产构建；Linux Chromium 15/1/2 三套浏览器测试；Windows Edge 原生部署套件。Docker 仅可选手动触发，本次未执行。真实样本兼容性不属于这些合成测试结论。

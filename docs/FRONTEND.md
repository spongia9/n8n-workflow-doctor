# Frontend / 前端

Vue 3、TypeScript、Vite、Router、Element Plus、Pinia、Vue Flow 1.48.2。真实 API 类型由 python -m tools.export_frontend_contract 生成，--check 检查漂移。

工作台、确认上传、诊断分组/筛选、Finding/规则侧栏、内部/跨工作流图及四报告下载均复用实际分析结果。Pinia 只保留有限内存会话，不存原文到浏览器持久存储。404 诚实显示过期/淘汰/重启。

开发：先启动 Python API 8000，在 frontend 执行 npm ci、npm run dev，访问 5173。正式使用根目录 start.ps1 的原生生产入口，npm run build 默认同源。

HTML 预览惰性解析后重建显示白名单，不执行脚本，不加载源 URL，保留空权限 iframe/CSP。图的布局和上下游可达关系来自后端；浏览器只绘制、筛选和高亮，大图拒绝超阈值渲染，不虚构动态目标。

测试与隔离端口见 [TESTING](TESTING.md)。

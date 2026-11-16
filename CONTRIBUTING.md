# Contributing / 贡献指南

先阅读双语 README、docs/SECURITY.md、docs/REPORT_FORMAT.md 和 docs/ROADMAP.md。

保持离线、只读和默认脱敏；不执行输入代码、不访问其 URL、不读取引用文件、不修改输入。结构规则或解析变更需要正常/边界/隐私回归；不能通过删测试或弱化断言掩盖失败。

完整开发安装使用 Python 3.12 的 pip install -e ".[api,test]"。提交前实际运行：

```text
python -m unittest discover -s tests -v
python -m tools.export_frontend_contract --check
python -m tools.review_public_files
python -m tools.review_history
```

frontend 中执行 npm ci、npm run typecheck、npm test、npm run build 及相应 Playwright 套件；见 docs/TESTING.md。格式不能改变扫描范围或退出码；新 API 字段优先向后兼容，统计单位必须说明。

只使用合成输入，真实工作流、凭证、日志、运行缓存和工具环境不进入提交。公开 JSON 采用逐文件白名单，新增样本须记录来源并核对原始字节。截图只接受已审查的合成数据画面。保留第三方版权和许可声明。

Pull requests should describe the concrete change, actual validation and remaining limits. Keep business analysis in the shared core and transports thin; retain bounded resources, read-only inputs and redacted output.

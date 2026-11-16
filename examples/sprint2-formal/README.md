# Synthetic examples / 合成示例

本目录包含合成输入或其脱敏报告，不是真实账号导出，不能据此宣称运行兼容。样本来源见 [provenance](../../docs/FIXTURE_PROVENANCE.md)。

```text
python -m workflow_doctor analyze examples/sprint2-formal/workflows --format json
python -m workflow_doctor analyze examples/sprint2-formal/workflows --format html --output reports/example.html
```

存在风险或未知时退出 1 属于正常诊断。旧报告保留原生成时结果，新规则/解释请重新运行到新输出路径；不要覆盖原始样本。

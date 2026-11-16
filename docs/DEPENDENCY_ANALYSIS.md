# Diagnostics and dependencies / 诊断与依赖

在安装 NetworkX 的 Python 3.12 环境使用 analyze；scan 保留基础结构检查。Graph MultiDiGraph 保留连接类型、输出/输入端口和多重边。图查询、SCC 与分层布局由后端完成；循环只作结构事实，不直接判错。

```text
python -m workflow_doctor analyze examples/sprint2-formal/workflows --format json
python -m workflow_doctor analyze examples/sprint2-formal/workflows --format graph-json
```

## 调用与依赖

适配器按节点类型/版本注册。Execute Workflow 1/1.1/1.2/1.3/1.4 的静态 ID、选择器、表达式及参数来源有明确分类；未支持版本保持未知，不猜测未来格式。Error Workflow 读取 settings.errorWorkflow，DEFAULT/空值不冒充 ID。文件/URL/内嵌工作流不被误当数据库 ID，不读取文件、不访问 URL、不求表达式运行值。

凭证、环境变量/n8n 变量、路径、HTTP(S) 源站等仅提取静态引用。凭证 ID 是引用，不是秘密；导出仍按指纹隐藏。外部相同源站只提示共享，不能证明是相同数据。

跨工作流使用唯一 n8n ID 的指纹解析；缺失/动态/重复身份使用明确的文件临时指纹。Found In Import Set 仅确认当前集合的静态匹配；Missing From Import Set 仅确认本次未包含；歧义/无效结构有单独状态。动态引用与未适配调用单列，不创建假目标。

## 规则目录

目录为静态应用数据，不接受输入定义规则；没有执行性插件来自工作流。每条规则包含检测对象/逻辑、风险、建议、局限、默认级别与置信度说明，界面点击 Rule ID 可查看。

| Rule ID | 名称 | 类别 | 默认对象 |
| --- | --- | --- | --- |
| WF001 | JSON 语法与编码检查 | structure | workflow |
| WF002 | 工作流结构校验 | structure | workflow |
| WF003 | 重复节点 ID | identity | node |
| WF004 | 重复节点名称 | identity | node |
| WF005 | 无效节点连接 | connection | connection |
| WF008 | 子工作流依赖需要核查 | workflow_dependency | node |
| WF009 | 错误工作流引用需要核查 | workflow_dependency | workflow |
| WF010 | 凭证引用需要重新配置 | credentials | node |
| WF011 | 疑似硬编码敏感参数 | security | node |
| WF012 | 变量引用需要核查 | variables | node |
| WF013 | 本地文件系统依赖需要核查 | filesystem | node |
| WF014 | Webhook 迁移配置需要核查 | webhook | node |
| WF015 | 第三方节点安装情况未知 | packages | node |
| WF016 | 目标环境兼容性未知 | environment | environment |
| WF018 | 共享外部资源引用提示 | shared_resource | node |

具体 Finding 的层级以实际证据为准：WF002 可以是工作流/节点/连线；WF010=node+credentials，WF013=node+filesystem，WF016=environment+unknown。严重程度、诊断状态、置信度和层级不可互换。置信度不是目标故障概率。

## 默认隐私

任意名称、ID、路径或参数可能含秘密，导出不恢复原始身份，保留来源别名、索引、已知类型与指纹。缺 ID 不编造实际 n8n ID；重复名称按位置与指纹区分。原始键路径采用序号扩展定位。详见 [报告](REPORT_FORMAT.md)、[API](API.md) 和 [安全](SECURITY.md)。

## 边界

不能据静态 JSON 验证目标版本、凭证有效性、文件可用性、权限或实际运行。未知不会被删除以减少风险数量。真实导出仍待明确授权验证；合成测试不建立真实兼容性保证。

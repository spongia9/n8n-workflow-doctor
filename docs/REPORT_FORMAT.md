# Report contract / 报告契约

CLI、API 下载和界面消费同一脱敏标准结果。基础 schema_version=0.2，analysis/graph schema_version=1.1；新增字段保持兼容，不改变扫描范围与 CLI 0/1/2 退出码。四种格式为 text/json/markdown/html；HTML 独立打开且脚本/远程资源禁用。

## 旧字段

根对象包括 input/file_count/finding_count/error_count/skipped_count/complete/results/skipped/errors/notice。根 finding_count 只统计 WF001–WF005。结构 Finding.to_dict 继续是 rule_id/severity/message/location/suggestion/location_details 六字段。

analysis.risks、summary.risk_count/manual_review_count 维持历史含义；checks 才是全部规范化检查，包含结构阻断、依赖、节点及目标环境未知项。不要把旧 API finding_count（全部检查）误当新问题 Finding 数。

## 定位与维度

规范化检查追加 finding_id、rule_name、scope/category、workflow_fingerprint/source_file/label/name、node_id/name/type/index/label、connection_source/target、parameter_path/evidence、中文说明/建议、unknown_reason/required_evidence/recommended_verification。

Rule ID 定义规则，FND- 加确定性指纹定义一次发现；同一有序输入集合与分析结果跨报告稳定，来源/内容/顺序变化可能改变身份。原始名称和 ID 默认不恢复；缺失 ID 使用明确的临时位置身份。path 中 {member:n}/{source:n}/{type:n} 是脱敏序号扩展，不声称是完整原键 JSONPath。

四个独立维度：assessment 保留 verified/blocked/risk/unknown/not_applicable；diagnostic_status 展示映射 pass/blocker/risk/unknown/not_applicable；severity_level 保守映射 error→high、warning→medium、info→low（不虚构 critical）；confidence 为提取证据强度。scope 是 workflow/node/connection/environment，category 是 credentials/filesystem 等。

## 统一统计

analysis.diagnostics.statistics 为唯一新计数来源：

- workflow_count：结构有效工作流对象数；内部节点和内部连线另计。
- check_count：全部检查；finding_count：blocked+risk+unknown；triggered_rule_count：这些问题的唯一规则数。
- assessment_counts：五状态合计等于 check_count。
- graph_node_count/graph_edge_count：跨工作流图，不与内部图混合。
- unresolved_reference_count：未解析静态引用记录；unresolved_target_count：唯一未解析目标。
- dynamic_dependency_count：真正动态表达式调用，不把未知版本当作动态。

同一目标的多个调用各有独立 dependency_id 与证据，图保留平行边；不是重复工作流对象。动态目标没有虚构节点或边。缺少导入目标不等于目标实例不存在。前端筛选只改变展示数量，不重定义全量统计。

图元数据包含证据、端口、循环组、布局、关联发现与依赖。静态上下游高亮为后端可达集合，不代表实际执行路径，不枚举所有简单路径。结构无效文件保留发现但不伪造节点图。

所有格式保持敏感值遗漏，转义动态文本，公开报告前仍应人工检查可见来源路径。HTML 的时间是呈现时间，不是目标实例验证时间。

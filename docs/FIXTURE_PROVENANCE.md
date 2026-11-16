# Fixture provenance / 样本来源

所有公开 JSON 都是合成工作流或其脱敏生成报告，不是从真实 n8n 账号导出的文件。凭证、Header、路径、ID、地址均为测试占位符，不执行这些模拟工作流。合成覆盖不证明真实导出/目标版本兼容。

真实样本只接受用户明确提供并授权的本地只读文件，留在忽略目录，绝不加入公共白名单、暂存或上传；仅公开脱敏结论。当前真实授权验证数量为 0。

以下 18 个 JSON 在公开准备中原始字节保持不变；新测试数据在代码内临时构造，不包含真实凭证。

| 文件 | SHA-256 |
| --- | --- |
| examples/sprint2-formal/dependency-graphs.json | cd91e709806e7113380170ff05cc56b023034d703864ffb3dcf5a14b49d84ad0 |
| examples/sprint2-formal/migration-report.json | a34593b3febac41ddb503fce2f41307a2cb3e6f488dc18cd062aad2cd3f7e9ab |
| examples/sprint2-formal/workflows/A.json | df7167003ac363e0bceb2f5ec5368abef6664df396e7d34cd1d40b10d0952334 |
| examples/sprint2-formal/workflows/B.json | 2d5a50d558ba8585a9216a80fb6f2c53f0d60a2b3b81980f725e9328c195ae0f |
| examples/sprint2-formal/workflows/C.json | 334bb549e9ee510052b74115c58d029c632d09852725d9f801f5815f72f9772b |
| examples/sprint2-formal/workflows/ERROR_HANDLER.json | 7b8d2187010687cf72dddc456eaafb0a5efaf885c0a532b282086010df754f59 |
| examples/sprint2/dependency-graphs.json | bedf059f1ff577cc3dbdd84a0614fd654bc783b49c7c58f2cfaa58d618c1193b |
| examples/sprint2/migration-report.json | e93242e9f8c51f4f51ea8aa62fae165791af6020358199236d2a65a5ab3699a8 |
| examples/sprint2/workflows/A.json | 84b1ccf457cf5ec20240816971507987eeb79a0b4e8dc59d59c393f0f60ea297 |
| examples/sprint2/workflows/B.json | d0e73c7d399e7a7e1ecc51446f45179b8794995bf656925a6aefb600b8e7f7c3 |
| examples/sprint2/workflows/C.json | f0bbb3027bdcef61e90c94d66b269eb708f30de474dd79ef5a82800a7b0addde |
| examples/sprint2/workflows/ERROR_HANDLER.json | 41c6f366d12245a169d2ea40edb496c36f56355350550880c6ae021d0f2695bc |
| examples/sprint3/migration-report.json | 89fcc6d07abcb340aec619f81700950fca919005de5e745f73ca661ce5cc0e0e |
| tests/fixtures/duplicate_id.json | 9b1714337682e2554631dc3cf5bd0e17d4cabf39af742ed6e47599e2abc2a14b |
| tests/fixtures/invalid.json | 3a65d13b63032ee9e2bed688e67fc4f1b7c265500c9c537732b3c6faccb57afe |
| tests/fixtures/missing_target.json | b63fd35e33b3cd369dfb982a0465b50394238b50c107ff2904c98e9dc3085e6f |
| tests/fixtures/valid.json | 4eb3ac820fefbc5ba2e224d2a177f88ed0901140f0d7903e409475f53c51a592 |
| tests/fixtures_compat/synthetic_export_shape.json | cea4d97ffcfca1ca4ccdfca678e92dfa602c02c273d88ff5638b28fc59b450ee |

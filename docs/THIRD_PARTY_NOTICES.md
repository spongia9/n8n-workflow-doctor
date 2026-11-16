# Third-party notices / 第三方声明

项目自己的源码采用根目录 MIT 许可证；第三方组件继续适用其原有许可，不以项目 MIT 替代。

Swagger UI v5.34.1 来自官方固定 tag，仅供离线 /docs： https://github.com/swagger-api/swagger-ui/tree/v5.34.1 。资源位于 src/workflow_doctor/api/assets，Apache-2.0 及依赖声明原字节保留，文件按固定 SHA-256 校验。见 [原始许可](../src/workflow_doctor/api/assets/LICENSE.txt) 和 [依赖声明](../src/workflow_doctor/api/assets/swagger-ui-bundle.js.LICENSE.txt)。运行不依赖 CDN。

Python 依赖见 pyproject.toml 与 deploy/backend 的哈希锁；前端及测试依赖见 frontend/package-lock.json。源码发布不包含 node_modules、虚拟环境、构建包或容器镜像。分发这些产物时仍需保留对应组件的通知和条款；本仓库不声称已完成镜像漏洞审计。

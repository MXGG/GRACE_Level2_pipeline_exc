# Services Compatibility Status

## Purpose

**English**

`python/grace_pipeline/services/` is no longer a canonical architecture layer. It is retained only as a temporary compatibility surface while old imports are migrated to the current package structure.

**中文**

`python/grace_pipeline/services/` 已不再是正式的架构层。目前保留它，只是为了在旧导入路径迁移到现行包结构期间提供临时兼容接口。

## Canonical Targets

| Package | English | 中文 |
| --- | --- | --- |
| `grace_pipeline.app` | Workflow orchestration | 工作流编排 |
| `grace_pipeline.domain` | Domain-facing interfaces | 面向领域层的接口 |
| `grace_pipeline.infra` | Runtime and data infrastructure | 运行时与数据基础设施 |
| `grace_pipeline.ui` | GUI and plotting | GUI 与绘图 |
| `grace_pipeline.compat` | Temporary import bridge | 临时导入桥接层 |

## Rules

**English**

- Do not add new business logic here.
- If an old import path must remain public, keep it as a thin forwarder only.
- New code should target the canonical packages listed above.

**中文**

- 不要在这里新增业务逻辑。
- 如果必须保留旧导入路径，也只能保留为轻量转发层。
- 新代码应直接依赖上面列出的正式包。

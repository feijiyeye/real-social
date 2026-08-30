# 可迁移运行说明

## 包身份

本目录是 `real-social` Skill 的可迁移发布包，界面显示名为“真实社交”。`runtime/` 是轻量启动和路由层；`knowledge/manifest.json` 仍是知识快照的文件清单、原始路径映射和 SHA-256 校验入口，但不属于普通聊天的默认读取集。

包内 `knowledge/` 是运行时唯一知识根目录。不要把安装机器上的 `/Users/...`、`/Volumes/...` 或旧的 AI workspace 路径当作运行时依赖。

## 目录约定

- `knowledge/01-原始资料/`：当前 Dragon 知识库已归档的原始资料、稳定文本、话术索引和审计文件。
- `knowledge/02-知识单元/`：真实社交相关知识单元；短视频等无关单元不随本包发布。
- `knowledge/03-动态索引/`：主题导航快照。
- `knowledge/04-系统/`：入库、检索、案例处理、项目续接和元数据规则。
- `knowledge/external-sources/`：当前知识单元仍引用的外部原件快照，包括旧体系文本、原始 SRT/DOCX、Apple Notes 原件和历史 V0 架构文件。
- `knowledge/_original_dragon_root/`：本次快照使用的 Dragon 根目录治理文件原件；运行时优先读 `knowledge/` 根部生成的可迁移治理文件。
- `runtime/runtime-entry.md`：普通调用的最小入口和硬边界。
- `runtime/route-index.json`：任务路由、状态路由、优先级和最小读取计划。
- `runtime/navigation-index.json`：任务完成后的单步导航规则。
- `runtime/unit-index.json`：知识单元的紧凑元数据索引，不复制正文。
- `runtime/phrase-route-index.json`：候选话术入口与路由分片；完整索引仅按需读取。
- `runtime/runtime-manifest.json`：运行时文件的独立哈希和计数。

聊天分析和回复默认遵循阶段导航优先契约：先区分 `observed`、`reported`、`inferred` 并输出阶段、方向、状态路由和反馈门控，只有明确要求可发送内容且边界满足时才进入少量示例；新反馈到达后重新判断。该契约由 `runtime/route-index.json` 的 `stage_navigation` 元数据发布，不改变候选单元状态。

## 路径解析

知识单元中的绝对路径是历史来源定位，不是跨机器依赖。需要回读时按以下顺序解析：

1. 普通聊天先使用 `runtime/unit-index.json` 中的包内路径；只有需要历史来源回读时才查 `knowledge/manifest.json` 的 `source_path_map`。
2. 命中映射后使用 `bundle_path`。
3. 没有精确映射时，用原路径的文件名在 `knowledge/01-原始资料/` 和 `knowledge/external-sources/` 中查找。
4. 找不到原件就标记来源不可回读，不用猜测或用相似文件替代。

## 更新与分发

当前包是发布快照，不是 Dragon 主库。源机器收到新材料并明确入库后，先在 Dragon 知识库完成查重、候选化和校验，再重新构建本包。正式流程规则 `K-20260826-001` 已纳入当前快照；不要直接在目标机器手工修改 `manifest.json` 或把候选单元改成 `canonical`。

在源机器上重新构建时，`scripts/build_bundle.py` 会先复制知识快照，再执行 `scripts/build_runtime_indexes.py` 生成 `runtime/`。路由配置唯一来源是 Dragon 的 `04-系统/真实社交运行时路由配置.json`；`runtime/` 下的文件均为可删除后重建的派生资产。

使用包前运行：

```bash
python3 scripts/validate_bundle.py .
python3 scripts/validate_knowledge.py knowledge/02-知识单元 \
  --manifest knowledge/04-系统/知识单元元数据兼容清单.json \
  --topic "男性情感聊天教学"
python3 scripts/route_request.py --text "用户当前输入"
```

包目录可直接复制到目标机器的 Codex Skills 目录，并以 `$real-social` 显式调用；界面中显示“真实社交”。

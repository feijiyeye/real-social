# real-social Skill

当前版本标记见 `VERSION`。

这是 `real-social` 的可安装 Skill 目录。它用于连续分析真实社交聊天，按照三阶段九步骤判断当前位置，并基于知识库给出方向、反馈门槛和下一步。

## 让 AI 帮你安装

把下面这段话发给能够访问 GitHub并操作本地文件的 AI：

> 请访问 https://github.com/feijiyeye/real-social，阅读仓库 README、skills/real-social/SKILL.md 和 VERSION。请把仓库里的 skills/real-social 安装到你当前环境的用户级 Skill 目录，只安装这个 Skill，不要修改其他 Skill。安装后检查 VERSION、SKILL.md、runtime、references、scripts 和 knowledge 是否完整，并告诉我是否需要重新打开会话。

## 让 AI 帮你更新

已经安装旧版本时，把下面这段话发给 AI：

> 请访问 https://github.com/feijiyeye/real-social，比较仓库 VERSION 和我本地 real-social 的 VERSION，并核对本地 SKILL.md 与 runtime-contract.md 是否包含仓库当前的普通用户视图规则和话术库原句功能状态。如果规则较旧，请先检查本地是否有自定义修改；有修改时先备份，再只更新 real-social。更新后检查 Skill 文档、runtime、窗口连续性和知识库锚定规则是否完整，并告诉我更新结果。

只有能够联网访问 GitHub、读取仓库并写入本地 Skill 目录的 AI 才能真正完成安装。只具备聊天能力的 AI 无法修改你的电脑。

安装或更新后，重新打开一个会话，再使用 `$real-social`。

## 主要能力

- 每轮重新识别三阶段九步骤。
- 同一个窗口连续记录阶段、计数、方向和反馈。
- 最近 12 轮保留详细记录，更早内容滚动压缩。
- 维护赋格和女方真性评估计数器。
- 默认只给方向，不生成 AI 改写回复。
- 默认使用普通用户视图，不展示检索文件、完整回执、内部路由字段或测试结果。
- 话术库原句功能当前关闭；不检索或展示原句，也不生成 AI 改写的可发送话术作为替代。
- 每轮重新检索知识库；缺少 `knowledge_trace` 时阻断模型自由发挥。
- 停止、拒绝、不适、安全、隐私、成年和同意边界优先。

需要检查知识库锚定、路由或测试信息时，请明确要求切换到诊断视图；普通调用只呈现当前判断和行动方向。

完整说明见仓库根目录的 [README](../../README.md)，版本变化见 [CHANGELOG](../../CHANGELOG.md)。

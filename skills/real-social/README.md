# 真实社交 Skill

这是一个可迁移的 Codex Skill 快照，适用于线上聊天分析、阶段判断、案例参考、来源审计和明确要求后的少量回复示例。

## 安装

### 推荐：终端一行安装

前置条件：Node.js 22.20.0 或更高版本（含 npm）。在终端执行：

```bash
npx -y skills add feijiyeye/real-social -g --all
```

这会安装公开仓库中的 `real-social` 到 `skills` CLI 支持的 Agent。只使用 Codex 时，可以限定目标：

```bash
npx -y skills add feijiyeye/real-social -g -s real-social -a codex -y
```

安装完成后重新打开一轮 Codex。`skills` CLI 重新安装时可能覆盖目标目录中的同名文件；如果你改过本地 Skill，请先备份。

## 快速调用

安装后重新打开一轮 Codex，使用：

```text
$real-social
请先分析这段聊天的证据、阶段和下一步方向，暂时不要生成可发送句子。
```

需要可发送内容时，请明确说明目标；Skill 会先完成阶段、状态和边界判断，再给 1-3 个当前上下文适配示例。只说“直接帮我回复”而没有目标时，会先做需求对齐。

## 默认工作顺序

```text
任务路由
→ 状态路由与硬边界
→ observed / reported / inferred
→ 阶段与候选分链
→ push / pull 或独立分流
→ 反馈门槛
→ 满足条件后才检索候选话术并给少量示例
```

停止、隐私/安全/成年/同意、回蓝、事实澄清、真实顾虑、低回应和邀约条件会优先于一般的 `push` / `pull` 请求。回蓝命中时只输出状态与暂停动作，不检索或生成回蓝话术。线下搭讪、肢体和现场升级资料只作上下文或来源审计，不直接路由为线上回复。

## 运行入口

普通调用先读取：

- `runtime/runtime-entry.md`
- `runtime/route-index.json`
- `runtime/unit-index.json`

按需读取：

- `runtime/navigation-index.json`：任务完成或收到新反馈时；
- `runtime/phrase-route-index.json`：方向明确且通过示例门槛后；
- `knowledge/02-知识单元/`：命中路由所需的少量知识单元；
- `knowledge/01-原始资料/` 和 `knowledge/external-sources/`：来源审计或上下文复核时。

包内路径均为相对路径。知识单元中的 `/Users/...`、`/Volumes/...` 是历史来源定位，不是安装机器的运行依赖。

## 包内脚本

```bash
python3 scripts/validate_bundle.py .
python3 scripts/validate_knowledge.py knowledge/02-知识单元 \
  --manifest knowledge/04-系统/知识单元元数据兼容清单.json \
  --topic "男性情感聊天教学"
python3 scripts/route_request.py --text "用户当前输入"
python3 scripts/search_phrases.py --route <route_id> --query "对方原消息" --limit 3
```

这些脚本只依赖 Python 3 标准库。`build_bundle.py` 和 `build_runtime_indexes.py` 用于源端重建发布快照；普通使用不需要执行它们。

## 目录

- `SKILL.md`：完整行为规则和输出契约
- `agents/openai.yaml`：Codex 界面元数据
- `runtime/`：轻量启动层、路由和派生索引
- `knowledge/`：可迁移知识快照、原始资料和来源映射
- `references/`：运行协议、处理流程和迁移说明
- `tests/`：路由和元数据回归测试

## 内容边界

当前快照包含原始聊天、课程/话术资料、Apple Notes 和第三方来源，可能含可识别上下文。使用前请确认隐私、版权和授权；不要据此识别、骚扰、施压或绕过他人的拒绝、不适、安全和同意边界。

当前版本没有独立 `LICENSE` 文件。公开可见不等于默认授予复制、再分发或商业使用许可，具体边界见仓库的 [NOTICE.md](https://github.com/feijiyeye/real-social/blob/main/NOTICE.md) 和 [README.md](https://github.com/feijiyeye/real-social/blob/main/README.md)。

## 版本

当前版本：[`0.1.0`](VERSION)。

完整行为规则见 [`SKILL.md`](SKILL.md)，运行协议见 [`references/portable-runtime.md`](references/portable-runtime.md) 和 [`references/policy.md`](references/policy.md)。

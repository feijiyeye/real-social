# real-social

> 面向 Codex 的真实社交聊天 Skill：把聊天文字、截图、SRT 或课程素材交给 Agent，先核对证据和边界，再判断阶段、候选分链与状态路由，最后决定下一步是 `push`、`pull` 还是独立分流。

[![Version](https://img.shields.io/badge/version-0.1.0-2563EB.svg?style=flat-square)](skills/real-social/VERSION)
[![Codex Skill](https://img.shields.io/badge/platform-Codex-111827.svg?style=flat-square)](skills/real-social/SKILL.md)
[![Public snapshot](https://img.shields.io/badge/release-public%20snapshot-16A34A.svg?style=flat-square)](NOTICE.md)

已验证：`skills` CLI 从公开 GitHub 仓库发现并隔离安装 `real-social`，以及 Codex 自带的 `skill-installer` 安装与运行。其他支持 Skills 的 Agent 尚未逐一验证。

[快速开始](#快速开始) · [能力一览](#能力一览) · [工作方式](#工作方式) · [安装](#安装) · [目录结构](#目录结构) · [校验](#校验) · [数据与边界](#数据与边界) · [贡献与反馈](#贡献与反馈)

## real-social 解决什么问题

它不是把单句“万能话术”直接塞给你的回复生成器。它先把当前聊天放回阶段和证据里，再判断是否适合推进、暂停、澄清、邀约或停止。

| 真实处境 | 你会得到 |
| --- | --- |
| 有一段聊天记录，但不知道已经完成了什么 | 区分 `observed`、`reported`、`inferred`，整理已完成事项、当前问题和阶段候选 |
| 不确定现在该推进、认可还是先留空间 | 根据状态路由给出 `push`、`pull` 或独立分流，并说明目的和反馈门槛 |
| 对方回复变少、提出顾虑或改期 | 进入低回应、真实顾虑/条件或邀约调度分流，不把沉默自动解释成兴趣 |
| 对方表达拒绝、不适、停止或安全疑虑 | 优先处理停止、隐私、安全、成年和同意边界，暂停不必要的话术检索 |
| 已经明确目标，确实需要可发送内容 | 在阶段、方向、上下文和边界都满足后，给出少量当前聊天适配示例 |
| 想找相似案例或核对原始来源 | 按路由召回少量案例、话术候选和相邻原始上下文，不把来源主张直接当成规则 |
| 有新素材需要长期保存 | 只有明确要求入库时才查重、保留来源并写入候选知识，不自动改写为正式规则 |

## 快速开始

安装完成并重新打开一轮 Codex 后，直接使用 `$real-social`：

### 只做分析

```text
$real-social
请先分析下面这段聊天，不要直接替我写回复。
请区分 observed、reported、inferred，判断当前阶段和最值得解决的问题，
并说明下一步适合 push、pull，还是应该进入顾虑、低回应或停止分流。

我：周末你一般怎么安排？
对方：看情况吧，最近有点忙。
我：那等你有空再说。
```

### 明确需要可发送示例

```text
$real-social
我明确需要 1-3 句可以发送的话。请先完成阶段和状态判断，
再从最匹配的一个方向给少量示例，并说明推送后要观察什么反馈。
以下是最近完整聊天：
……
```

如果只说“直接帮我回复”但没有说明目标，Skill 会先对齐你想达成的结果、语气和顾虑，不会随机替你选择方向。

## 能力一览

### 任务路由

| 入口 | 用途 | 典型产出 |
| --- | --- | --- |
| `first_use` | 首次使用与入口说明 | 最小调用方式、输入要求和可用范围 |
| `analyze_chat` | 聊天分析与阶段判断 | 证据层、阶段候选、当前问题和下一步 |
| `reply_request` | 回复方向与少量示例 | 方向选择、反馈门槛和 1-3 个适配示例 |
| `case_lookup` | 相似案例检索 | 相邻案例、适用条件和限制 |
| `source_audit` | 素材与来源审计 | 原文位置、来源层级和可回读范围 |
| `ingest_material` | 素材入库与查重 | 重复判断、候选知识单元和来源关系 |
| `architecture_maintenance` | 架构、路由与维护 | 发布包、运行索引和迁移问题的检查结果 |

### 状态路由

状态按优先级处理，高优先级会覆盖一般的“帮我回复”请求：

| 状态 | 含义 | 默认处理 |
| --- | --- | --- |
| `stop_boundary` | 明确拒绝、停止、删除或不要再联系 | 停止推进，尊重边界 |
| `privacy_safety_age_consent` | 隐私、安全、成年、身份或同意未核实 | 先核对风险，不进入高风险话术 |
| `recovery` | 焦虑、耗竭或冲动投入触发回蓝闸门 | 只提示暂停恢复，不检索回蓝话术 |
| `clarify` | 事实错误、误会、伤害或意图澄清 | 转入真实澄清、责任与修复 |
| `concern_condition` | 顾虑、疲劳、交通、时间或现实条件 | 承接顾虑，核对双方是否方便 |
| `low_response` | 连续低回应、缺少主动延展或暂时断联 | 减少投入，重新评估是否暂停或重启 |
| `invite` | 双向兴趣和条件可能支持邀约 | 核对时间、地点、方便与安全 |
| `interest_push_pull` | 兴趣证据收集阶段 | 仅在条件满足时选择 `push` 或 `pull` |
| `unknown_stage` | 证据不足或阶段冲突 | 先补齐关键上下文，不猜测 |

## 工作方式

```text
聊天文字 / 截图 / SRT / 素材
          ↓
      任务路由
          ↓
   状态优先级与硬边界
          ↓
 observed / reported / inferred
          ↓
   阶段节点与候选分链
          ↓
 push / pull 或独立分流
          ↓
 反馈门槛与继续/切换/暂停条件
          ↓
 满足门槛后才给少量示例
```

核心约束：

- 聊天分析和回复默认先做阶段导航，再决定是否给句子；收到新反馈后重新判断，不机械延续上一条建议。
- 兴趣证据收集阶段对外只展示 `push` / `pull`；真实顾虑、低回应、邀约、停止和安全问题走独立分流。
- `push` 的目标是轻度张力和获得可观察反馈，不以焦虑、嫉妒或情绪失衡为目标；不设固定推拉比例，也不授权连续加推。
- 对方明确只做朋友、没有恋爱意向、拒绝或不舒服时，不用技巧强行回锚或重启。
- 回蓝是恢复闸门，不是第三种聊天方向，也不授予重新联系许可。
- 线下搭讪、肢体、眼神和现场升级材料只作上下文或来源审计，不直接路由为线上回复。
- 原始资料、来源观点和 `candidate` 知识单元用于参考和审计，不自动等于正式规则、事实保证或效果承诺。

## 安装

### 推荐：终端一行安装

前置条件：Node.js 22.20.0 或更高版本（含 npm）。在终端执行：

```bash
npx -y skills add feijiyeye/real-social -g --all
```

这条命令会从公开 GitHub 仓库发现 `skills/real-social`，并全局安装到 `skills` CLI 支持的 Agent 目录。安装完成后重新打开一轮 Codex，再使用 `$real-social`。

如果只使用 Codex，建议限定安装目标：

```bash
npx -y skills add feijiyeye/real-social -g -s real-social -a codex -y
```

其中 `-g` 表示全局安装，`--all` 表示所有支持的 Agent，`-s real-social` 指定这个 Skill，`-a codex` 指定 Codex。`npx` 会临时下载 `skills` CLI，不需要预先全局安装它。

`skills` CLI 重新安装时可能覆盖目标目录中的同名文件。若你改过本地 Skill，请先备份或确认目标目录后再执行；不要把公开仓库内容直接覆盖到含有个人修改的目录。

### Codex 专用备用方式

如果不想使用 Node.js/npm，也可以使用 Codex 自带的 `skill-installer`：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo feijiyeye/real-social \
  --path skills/real-social
```

如果你的 Codex 使用自定义 `CODEX_HOME`，将命令中的 `~/.codex` 替换为对应目录。这个安装器默认把 Skill 放到 Codex 的 `skills` 目录；目标目录已存在时会停止，不会自动覆盖。安装完成后重新打开一轮 Codex，再使用 `$real-social`。

## 目录结构

```text
skills/real-social/
├── SKILL.md                 # Skill 入口与行为规则
├── agents/openai.yaml       # Codex 界面显示名与默认调用提示
├── runtime/                 # 轻量入口、任务/状态路由和按需索引
├── knowledge/               # 本次可迁移的知识快照与来源映射
├── references/              # 运行协议、处理流程和迁移说明
├── scripts/                 # 路由、检索、构建和校验脚本
├── tests/                   # 运行时路由与元数据回归测试
├── README.md                # 安装后的包内快速参考
└── VERSION                 # 当前版本
```

运行时使用包内相对路径，不依赖安装机器上的 `/Users/...` 或 `/Volumes/...` 历史路径。普通聊天先读取 `runtime/` 的轻量入口，再按路由按需读取 `knowledge/`。

## 校验

在仓库根目录运行：

```bash
python3 skills/real-social/scripts/validate_bundle.py skills/real-social
python3 skills/real-social/scripts/validate_knowledge.py \
  skills/real-social/knowledge/02-知识单元 \
  --manifest skills/real-social/knowledge/04-系统/知识单元元数据兼容清单.json \
  --topic "男性情感聊天教学"
python3 -m unittest discover -s skills/real-social/tests -v
```

也可以检查路由：

```bash
python3 skills/real-social/scripts/route_request.py \
  --text "请分析这段聊天并判断下一步"
```

`0.1.0` 发布快照的验收结果：

- `validate_bundle.py`：`checked=245 errors=0`
- `validate_knowledge.py`：`checked=49 errors=0 warnings=2`；两条警告是已登记的旧元数据兼容项
- 回归测试：42 项全部通过
- Skill Installer 冷启动下载：263 个文件，安装后与发布包逐文件哈希一致

脚本只使用 Python 3 标准库；脚本用于构建、路由、检索和校验，不是聊天运行时的额外服务依赖。

## 数据与边界

> **公开完整快照提醒**：本仓库包含原始聊天转写、课程和话术资料、Apple Notes 来源、第三方素材及可能可识别的聊天上下文。公开后已经被下载的副本无法撤回。使用前请自行确认隐私、版权和授权范围。

请勿使用仓库内容识别、骚扰、施压、诱导或绕过他人明确表达的拒绝、不适、安全和同意边界。Skill 不连接聊天平台，不代表用户发送消息，也不保证任何关系或沟通结果。

当前仓库没有独立 `LICENSE` 文件。公开可见不等于默认授予复制、再分发或商业使用许可；除作者明确授权外，以 [NOTICE.md](NOTICE.md) 中的使用边界为准。

完整行为规则见 [SKILL.md](skills/real-social/SKILL.md)，运行边界和迁移约定见 [references/policy.md](skills/real-social/references/policy.md) 与 [portable-runtime.md](skills/real-social/references/portable-runtime.md)。

## 贡献与反馈

欢迎通过 [Issues](https://github.com/feijiyeye/real-social/issues) 提交安装问题、路由错误或文档建议。

提交 Issue 或 Pull Request 时：

- 不要上传真实姓名、联系方式、截图原件或其他可识别个人的信息；
- 不要提交密码、验证码、API key、token 或平台账号资料；
- 保留来源、授权和上下文说明，避免把单个案例直接升级为普遍规则；
- 涉及原始聊天或第三方材料时，先确认你拥有公开和再分发权限。

## 版本

当前版本：[`0.1.0`](skills/real-social/VERSION)。版本文件记录包版本；路由索引和知识快照属于该版本的发布内容。仓库暂未维护独立 CHANGELOG，具体变更以 [提交记录](https://github.com/feijiyeye/real-social/commits/main) 为准。

## 作者与使用许可

仓库维护者：[@feijiyeye](https://github.com/feijiyeye)。

本项目目前按完整公开快照分发，但不附带默认的复制、再分发或商业使用许可。具体边界见 [NOTICE.md](NOTICE.md)。

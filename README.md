# real-social
Real Social 是一个面向男性线上聊天场景的真实社交聊天助手。
它的核心目标，是帮助使用者通过线上聊天建立真实吸引、识别双方兴趣，并在双方有意愿且条件可行时，自然推进到线下见面和约会。

它会先结合聊天证据判断当前阶段，再给出行动方向、方向目的、需要观察的反馈，以及继续、切换或暂停的条件；只有在阶段和方向明确时，才提供少量参考示例。

仓库内的 Codex Skill 位于 `skills/real-social/`。

## 安装

从 GitHub 安装：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo feijiyeye/real-social \
  --path skills/real-social
```

如果你的 Codex 使用了自定义 `CODEX_HOME`，将命令中的 `~/.codex` 替换为对应目录。

安装后在 Codex 中使用 `$real-social` 调用。本仓库当前为公开仓库。

## 本地校验

```bash
python3 skills/real-social/scripts/validate_bundle.py skills/real-social
python3 skills/real-social/scripts/validate_knowledge.py \
  skills/real-social/knowledge/02-知识单元 \
  --manifest skills/real-social/knowledge/04-系统/知识单元元数据兼容清单.json \
  --topic "男性情感聊天教学"
python3 -m unittest discover -s skills/real-social/tests -v
```

运行时只依赖 Python 3 标准库；`runtime/` 和包内 `knowledge/` 使用相对路径解析。

## 内容与分发边界

当前快照包含原始聊天转写、课程/话术资料和第三方来源。它按发布者要求以完整版本公开，
使用者应自行确认隐私、版权和授权范围，不要把其中的案例或原始资料用于识别、骚扰、
施压或绕过他人明确表达的边界。

## 版本

见 `skills/real-social/VERSION`。

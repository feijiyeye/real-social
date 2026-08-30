# real-social

用于 Codex 的“真实社交” Skill。仓库内的 Skill 位于 `skills/real-social/`。

## 安装

从 GitHub 安装：

```bash
python3 /path/to/install-skill-from-github.py \
  --repo feijiyeye/real-social \
  --path skills/real-social
```

安装后在 Codex 中使用 `$real-social` 调用。安装脚本来自 Codex 的
`skill-installer`，私有仓库需要当前 Git 凭据或 `GITHUB_TOKEN` / `GH_TOKEN`。

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

当前快照包含原始聊天转写、课程/话术资料和第三方来源。它是授权接收者使用的
私有发布候选，不应在完成隐私、版权和授权审查前设为公开仓库或转发给他人。
仓库可见性、素材范围和授权责任由发布者确认。

## 版本

见 `skills/real-social/VERSION`。

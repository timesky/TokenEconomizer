<style>
body, .markdown-body, .markdown-preview-view, .markdown-preview-section, #write, article, main, .container, .page { max-width: none !important; }
table, pre, .mermaid, img, svg { max-width: 100%; }
pre, .mermaid { overflow-x: auto; }
</style>

# TokenEconomizer — CodeBuddy CLI 适配追踪

本文件只存在于 `codebuddy-cli-adapt` 分支，不属于上游原版。用于记录适配分支的每一次改进及其对应的上游基准，便于回溯与对齐。

## 分支与远端

| 对象 | 标识 | 规则 |
|---|---|---|
| `main` | 镜像分支 | 只从 `upstream/main` 快进同步；**禁止**在 main 上提交任何适配改动 |
| `codebuddy-cli-adapt` | 适配分支 | 从 `main` 分出；适配改动只提交到这里；定期合并 `main` |
| `origin` | `git@github.com:timesky/TokenEconomizer.git` | fork，可写（分支与 tag 推送到这里） |
| `upstream` | `https://github.com/microsoft/TokenEconomizer.git` | 原版，只读 |

## 定期同步原版主分支

推荐节奏：每周一次，或在原版有新 tag 后立即同步。标准命令：

```bash
cd ~/workspace/github/TokenEconomizer

# 1) 拉取上游（含 tag）
git fetch upstream --tags

# 2) 检查差异（先看再动）
git log --oneline main..upstream/main

# 3) 主分支只做快进；若出现分叉说明 main 被污染，应停止并排查
git checkout main
git merge --ff-only upstream/main
git push origin main

# 4) 把上游进展并入适配分支
git checkout codebuddy-cli-adapt
git merge main        # 或 rebase main，取决于是否已推送过适配提交
```

也可用脚本完成第 1–3 步（含安全校验）：

```bash
bash scripts/sync-upstream.sh          # 只同步 main 到 origin
bash scripts/sync-upstream.sh --check  # 只检查，不改动
```

同步后若上游改动了适配分支Touch过的文件（当前预判为 `tokeneconomizer/plugin/hosts.py`、`tokeneconomizer/trace/*`），需人工解决冲突，不可直接 `--ours`/`--theirs` 覆盖。

## Tag 规范

**命名**：`codebuddy-v<MAJOR>.<MINOR>.<PATCH>+te-<上游短 SHA>`

- `codebuddy-vX.Y.Z`：适配分支自身的语义版本，每次改进递增；
- `+te-<短 SHA>`：本次改进所基于的上游 commit，作为 semver build metadata；
- 使用 **annotated tag**（`git tag -a`），message 中必须写明：上游仓库、基准 commit 全 SHA、基准日期、上游 tag（若有）、本次改动摘要。

含义：给定一个适配 tag，可直接回答"这次改进对应原版的哪个版本"。

创建示例：

```bash
git tag -a codebuddy-v0.2.0+te-<新短SHA> \
  -m "CodeBuddy CLI adaptation v0.2.0

Upstream: microsoft/TokenEconomizer
Base commit: <全 SHA> (main, YYYY-MM-DD)
Upstream tag: <tag 名或 none>
Changes:
- ..."

git push origin codebuddy-v0.2.0+te-<新短SHA>
```

## 改进追踪表

| 适配 Tag | 日期 | 基准上游 commit | 上游 tag | 改动摘要 |
|---|---|---|---|---|
| `codebuddy-v0.1.0+te-1bfeccd` | 2026-11-20 | `1bfeccdcecf48333b22762ad1dd9e36c6dc065df` | `v0.1.0`（`ec8ff5e`，落后基准 369 commits） | 建立分支隔离、同步脚本与 tag 追踪框架；尚无插件代码改动 |

> 上游目前仅有一个正式 tag `v0.1.0`（2026-10-26），之后 369 个提交未再打 tag。因此"对应原版版本"以 commit SHA 为准，tag 名仅作辅助参考。

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
| `codebuddy-v0.2.0+te-1bfeccd` | 2026-11-20 | `1bfeccdcecf48333b22762ad1dd9e36c6dc065df` | 同上 | 新增 CodeBuddy CLI 宿主适配：shim 运行时注入（零改原库）、transcript 解析器、成本映射、插件清单/hooks、离线单测 |
| `codebuddy-v0.3.0+te-1bfeccd` | 2026-11-20 | `1bfeccdcecf48333b22762ad1dd9e36c6dc065df` | 同上 | 实现无感安装：新增根级 marketplace 清单、manifest 的 `hooks` 路由、bootstrap 从回溯 clone 定位 shim；附 QUICKSTART.md。修复"装上也不走 shim"的隐藏缺陷 |
| `codebuddy-v0.3.1+te-1bfeccd` | 2026-11-20 | `1bfeccdcecf48333b22762ad1dd9e36c6dc065df` | 同上 | 真实安装修复：CodeBuddy 把 lib symlink 复制成实体目录致 core 落在 cache 内，_addon_root 增加 marketplace source 回溯以定位 shim。**本机已真实安装并验证** |

> 上游目前仅有一个正式 tag `v0.1.0`（2026-10-26），之后 369 个提交未再打 tag。因此"对应原版版本"以 commit SHA 为准，tag 名仅作辅助参考。

## CodeBuddy 适配架构（v0.2.0）

**注入路线**：纯 shim 注入，`tokeneconomizer/` 原库文件零改动。`codebuddy/shim.py::install()` 在启动时向原库内存注册表注入宿主类、检测规则、env 白名单与标签；`plugin/scripts/codebuddy_bootstrap.py` 先注入再调用原 `hook.main`/`cli.main`。上游 `git pull` 不会与适配文件冲突。

**机制范围**：

| 机制 | 状态 | 依据 |
|---|---|---|
| Micro-skills（跨会话学习） | 启用 | SessionStart / UserPromptSubmit 的 `additionalContext` 已验证到达模型；会话可转成 Claude-shaped trace 供机制层 fold |
| Loop guard（失败循环干预） | 启用 | 依赖 prompt_context 与 prompt-turn 判定，均已适配 |
| 成本统计 | 启用 | `rawUsage` 映射：cache 读优先取 `prompt_cache_hit_tokens`（Anthropic 名字段是 0 占位），input 取 `prompt_cache_miss_tokens`；非 Anthropic 模型走 fallback 计价 |
| Tool pruning（工具裁剪） | **关闭** | CodeBuddy settings 的 deny 规则接口未经实测，按边界纪律不写入用户配置；与 Cursor/Grok/Antigravity 的实验性支持一致 |

**已验证事实**（见 `tests/test_codebuddy_adapter.py`，9 项全过）：宿主注册/检测、Claude Code 回退不受影响、transcript→trace 形状转换、上游 `load_trajectory` 兼容、失败结果标记、usage 字段映射与去重、prompt 计数排除 tool_result、CLI `--host codebuddy`。原库核心回归测试 213 项零回归。端到端 payload 经完整 hook 链无异常（fail-open 契约保持）。

**已知边界**：`codebuddy/host.py` 中会话 ID 与 cwd 取自 hook payload；`history()` 读取 `~/.codebuddy/projects`（或 `CODEBUDDY_CONFIG_DIR`）。端到端安装到本机 CodeBuddy CLI 未在本轮执行（按约定只做离线单测 + 真实 transcript 回放）。

## 无感安装机制（v0.3.0）

安装流程见 [`QUICKSTART.md`](QUICKSTART.md)，与原版同构：克隆 → `plugin marketplace add` → `plugin add`。三处关键设计使适配在无人工干预下生效：

| 环节 | 实现 | 依据 |
|---|---|---|
| 市场入口 | 新增根级 `.codebuddy-plugin/marketplace.json`（市场名 `tokeneconomizer-codebuddy`，源 `./plugin`） | 实测 `codebuddy plugin marketplace add "$PWD"` 成功识别该清单 |
| hooks 路由 | `plugin/.codebuddy-plugin/plugin.json` 增加 `"hooks": "./hooks/codebuddy-hooks.json"` | CodeBuddy 二进制支持 manifest 的 `hooks` 字段（path/object/array），按 `join(plugin_root, path)` 解析；原版 cursor/codex/copilot 均用此模式 |
| 复制安装后定位 shim | `codebuddy_bootstrap._addon_root(core)` 优先从 core（回溯到的 clone 根）定位 `codebuddy/` 包 | CodeBuddy 只复制 `plugin/` 到 `cache/<market>/<plugin>/<ver>`，shim 不随复制；原版 `_marketplace_sources()` 从 `known_marketplaces.json` 回溯到 clone |

**代价**：克隆必须原位保留（与原版 "leave it in place" 要求一致）——核心库与 shim 都从它定位。

**验证**（临时 HOME + 真实 cache 层级模拟）：`marketplace add` 真实执行成功；模拟复制安装后 core 回溯到 clone、shim 可发现、宿主注册成功；SessionStart payload 经完整 hook 链 exit 0、输出 `{}`、无 errors.log。受限网络下 `plugin add` 会因 CLI 内部配置拉取失败（`fetch config failed` / `No mapping found`）而不可用，属 CLI 环境问题，与插件无关。

### 上游同步后的适配维护

原库文件零改动 ⇒ `git merge upstream/main` 通常无冲突。需人工复核的注入点集中在 `codebuddy/shim.py` 引用的原库符号：`hosts.HOSTS`、`hosts.detect`、`hosts.default_host`、`config._ENV`、`history.HOST_LABEL`。上游若改名，install() 会降级记入 `codebuddy.shim.warnings()` 而非抛错；升级时应检查该列表。

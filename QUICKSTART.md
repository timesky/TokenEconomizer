<style>
body, .markdown-body, .markdown-preview-view, .markdown-preview-section, #write, article, main, .container, .page { max-width: none !important; }
table, pre, .mermaid, img, svg { max-width: 100%; }
pre, .mermaid { overflow-x: auto; }
</style>

# TokenEconomizer — CodeBuddy CLI 快速安装

本文件只存在于 `codebuddy-cli-adapt` 分支。安装流程与原版一致：**克隆 → 添加本地市场 → 安装插件**，共三条命令。装完即用，无需手动注入 shim、无需设置环境变量。

## 安装（与原版一致）

在你想保留克隆的目录下执行。**克隆必须留在原处**——插件核心库通过它定位（与原版要求相同）。

```sh
git clone -b codebuddy-cli-adapt https://github.com/timesky/TokenEconomizer.git
cd TokenEconomizer
codebuddy plugin marketplace add "$PWD"
codebuddy plugin install tokeneconomizer-codebuddy@tokeneconomizer-codebuddy
```

说明：

- `marketplace add "$PWD"` 读取仓库根的 `.codebuddy-plugin/marketplace.json`，市场名为 `tokeneconomizer-codebuddy`。
- `plugin install <插件>@<市场>` 与原版 `codex plugin install tokeneconomizer@tokeneconomizer` 同构，只是 CLI 名与市场名不同。本机 CLI 的 `plugin add` 子命令请求了未注册的 endpoint，须用 `plugin install`。
- 安装后务必确认插件已启用：检查 `~/.codebuddy/settings.json` 的 `enabledPlugins` 是否含 `tokeneconomizer-codebuddy@tokeneconomizer-codebuddy: true`。沙箱下安装收尾删锁会失败，可能导致文件复制了但未启用——排查见下方"重启后命令仍不出现"。
- 首次在某个 CodeBuddy 版本上使用时，若提示信任插件/文件夹，选择信任（与原版的 "Yes, I trust this folder" 一致）。

## 验证

启动 CodeBuddy 后，在任意仓库中运行状态命令确认：

```
/tokeneconomizer:status
```

或直接从克隆验证宿主识别与注入（离线，不启动 CodeBuddy）：

```sh
cd TokenEconomizer
PYTHONPATH=. python3.11 -c "
from codebuddy.shim import install; install()
from tokeneconomizer.plugin import hosts
print("codebuddy registered:", "codebuddy" in hosts.HOSTS)
"
```

输出 `codebuddy registered: True` 即注入生效。

## 斜杠命令

装好后重启 CodeBuddy，命令面板应出现以下 7 个命令（带 `tokeneconomizer:` 命名空间，不与内置命令冲突）：

| 命令 | 作用 |
|---|---|
| `/tokeneconomizer:status` | 本仓库已学到的内容、机制状态与开销 |
| `/tokeneconomizer:microskills` | 会话开始时注入的仓库事实（micro-skills） |
| `/tokeneconomizer:facts` | 上者的旧名，向后兼容 |
| `/tokeneconomizer:config` | 查看/修改各机制开关与阈值，如 `set microskills=on` |
| `/tokeneconomizer:repos` | 列出所有已记录状态的仓库，`migrate` 可迁移旧键 |
| `/tokeneconomizer:toolprune` | 工具裁剪（CodeBuddy 上返回"不可用"，属预期） |
| `/tokeneconomizer:untool` | 上者的旧名，向后兼容 |

命令位于插件的 `codebuddy-commands/tokeneconomizer/` 子目录，由 manifest 的 `commands` 字段指向；CodeBuddy 按 `子目录:文件名` 生成命令名。目录不叫 `commands/` 是因为后者是原库给 Codex 保留的（会被当成 skills 重复加载，原库有测试强制断言该目录不存在）。命令体用 `!` 内联执行，调用 `te-codebuddy --host codebuddy`，与各宿主状态隔离。

### 重启后命令仍不出现？先查插件是否被加载

命令不显示**通常不是命令目录的问题，而是插件根本没被加载**。CodeBuddy 只加载 `settings.json` 里 `enabledPlugins` 标记为 `true` 的插件。在 WorkBuddy 沙箱里，安装收尾删锁目录会被 safe-delete 拦截并报 `Lock file is already being held`，导致文件复制进 cache 了、但 `enabledPlugins` 没写入——表现为"装了却什么都没有"。

按此顺序排查：

```sh
# 1) 插件是否在 enabledPlugins（关键）
python3 -c "import json,os; d=json.load(open(os.path.expanduser('~/.codebuddy/settings.json'))); print(d['enabledPlugins'].get('tokeneconomizer-codebuddy@tokeneconomizer-codebuddy'))"
# 输出 True 才对；若为 None，补写：
python3 -c "
import json,os
p=os.path.expanduser('~/.codebuddy/settings.json'); d=json.load(open(p))
d['enabledPlugins']['tokeneconomizer-codebuddy@tokeneconomizer-codebuddy']=True
t=p+'.tmp'; json.dump(d,open(t,'w'),ensure_ascii=False,indent=2); os.replace(t,p)
print('written:',json.load(open(p))['enabledPlugins']['tokeneconomizer-codebuddy@tokeneconomizer-codebuddy'])
"
```

补写后重启 CodeBuddy。可在 `~/.codebuddy/logs/<日期>/` 的日志里搜 `PluginLoaderManager` 与 `tokeneconomizer`，出现 `Loaded plugin components for tokeneconomizer-codebuddy...: 7 command(s)` 即加载成功。若仍不显示，再检查 `~/.codebuddy/plugins/cache/.../<版本>/codebuddy-commands/tokeneconomizer/` 是否存在——手动同步时从克隆的 `plugin/codebuddy-commands/` 复制即可。

## 与原版安装对照

| 步骤 | 原版（Claude Code） | 本适配（CodeBuddy CLI） |
|---|---|---|
| 克隆 | `git clone https://github.com/microsoft/TokenEconomizer.git` | `git clone -b codebuddy-cli-adapt https://github.com/timesky/TokenEconomizer.git` |
| 加市场 | `claude plugin marketplace add "$PWD/TokenEconomizer"` | `codebuddy plugin marketplace add "$PWD"` |
| 装插件 | `claude plugin install tokeneconomizer@tokeneconomizer` | `codebuddy plugin install tokeneconomizer-codebuddy@tokeneconomizer-codebuddy` |
| 信任文件夹 | Yes, I trust this folder | 信任插件/文件夹 |

差异仅在 CLI 名、市场名与 `-b` 分支参数；命令形态与安装顺序完全一致，其余无感。

## 为什么能无感

- **宿主识别自动注入**：`codebuddy-hooks.json`（由 manifest 的 `hooks` 字段路由）调用 `te-hook-codebuddy`，它先加载 shim 再进入原版 hook 链，运行时注册 `codebuddy` 宿主与 trace 解析器。
- **核心库定位**：CodeBuddy 安装时只复制 `plugin/`，核心库 `tokeneconomizer/` 靠 `known_marketplaces.json` 记录的市场源路径回溯到原克隆；`codebuddy_bootstrap.py` 从同一克隆找到 shim 包。因此**克隆不可删除或移动**（与原版一致）。
- **零改原库**：`tokeneconomizer/` 与原版所有 manifest/hooks 均未改动；适配全部由新增文件承载，上游同步零冲突。
- **宿主隔离**：学到的状态以 `codebuddy` 命名空间隔离，不与 Claude Code 混用；tool pruning 在本宿主关闭（无实测 deny 接口）。

## 更新与卸载

```sh
# 更新：拉适配分支最新代码，重新安装
cd TokenEconomizer
git pull origin codebuddy-cli-adapt
codebuddy plugin install tokeneconomizer-codebuddy@tokeneconomizer-codebuddy

# 卸载：移除插件（CLI 侧），按需删除学习状态
codebuddy plugin remove tokeneconomizer-codebuddy@tokeneconomizer-codebuddy
rm -rf ~/.tokeneconomizer   # 可选；会删除所有宿主学到的状态
```

> 环境备注：在部分受限网络/沙箱中，CLI 的 `plugin add` 会因内部配置拉取失败（表现为 `fetch config failed` / `No mapping found: POST /internal/plugin/add`）而无法完成安装。这是 CLI 自身的配置问题，与插件无关；`marketplace add` 为纯本地操作不受影响。请在正常网络环境下安装。

版本对应见 [`ADAPTATION.md`](ADAPTATION.md) 的改进追踪表与 tag 说明。

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
codebuddy plugin add tokeneconomizer-codebuddy@tokeneconomizer-codebuddy -y
```

说明：

- `marketplace add "$PWD"` 读取仓库根的 `.codebuddy-plugin/marketplace.json`，市场名为 `tokeneconomizer-codebuddy`。
- `plugin add <插件>@<市场>` 与原版 `codex plugin add tokeneconomizer@tokeneconomizer` 同构，只是 CLI 名与市场名不同。
- `-y` 确认启用插件代码；不加时 CLI 会交互式询问。
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

## 与原版安装对照

| 步骤 | 原版（Claude Code） | 本适配（CodeBuddy CLI） |
|---|---|---|
| 克隆 | `git clone https://github.com/microsoft/TokenEconomizer.git` | `git clone -b codebuddy-cli-adapt https://github.com/timesky/TokenEconomizer.git` |
| 加市场 | `claude plugin marketplace add "$PWD/TokenEconomizer"` | `codebuddy plugin marketplace add "$PWD"` |
| 装插件 | `claude plugin install tokeneconomizer@tokeneconomizer` | `codebuddy plugin add tokeneconomizer-codebuddy@tokeneconomizer-codebuddy -y` |
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
codebuddy plugin add tokeneconomizer-codebuddy@tokeneconomizer-codebuddy -y

# 卸载：移除插件（CLI 侧），按需删除学习状态
codebuddy plugin remove tokeneconomizer-codebuddy@tokeneconomizer-codebuddy
rm -rf ~/.tokeneconomizer   # 可选；会删除所有宿主学到的状态
```

> 环境备注：在部分受限网络/沙箱中，CLI 的 `plugin add` 会因内部配置拉取失败（表现为 `fetch config failed` / `No mapping found: POST /internal/plugin/add`）而无法完成安装。这是 CLI 自身的配置问题，与插件无关；`marketplace add` 为纯本地操作不受影响。请在正常网络环境下安装。

版本对应见 [`ADAPTATION.md`](ADAPTATION.md) 的改进追踪表与 tag 说明。

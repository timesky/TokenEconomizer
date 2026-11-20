#!/usr/bin/env bash
# 同步 fork 的 main 分支到上游 microsoft/TokenEconomizer。
# 只在 main 上做快进合并；适配分支的合并需人工执行，避免污染 main。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

UPSTREAM="upstream"
ORIGIN="origin"
MAIN="main"
CHECK_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    -h|--help)
      echo "用法: $(basename "$0") [--check]"
      echo "  --check  只检查差异，不改动工作区"
      exit 0 ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

if ! git remote get-url "$UPSTREAM" >/dev/null 2>&1; then
  echo "缺少 upstream 远端" >&2; exit 1
fi

echo "[1/4] 拉取上游与 tag ..."
git fetch "$UPSTREAM" --tags --quiet

echo "[2/4] 检查 main 与上游差异 ..."
if git diff --quiet "$MAIN" "$UPSTREAM/$MAIN"; then
  echo "  已是最新，无需同步。"
  exit 0
fi

AHEAD=$(git rev-list --count "$UPSTREAM/$MAIN..$MAIN")
BEHIND=$(git rev-list --count "$MAIN..$UPSTREAM/$MAIN")
echo "  main 领先 $AHEAD / 落后 $BEHIND"

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo "--check 模式：仅展示，不改动。"
  git log --oneline --no-decorate "$MAIN..$UPSTREAM/$MAIN"
  exit 0
fi

if [ "$AHEAD" -ne 0 ]; then
  echo "main 领先上游 $AHEAD 个提交，无法快进。请先排查 main 是否被意外提交。" >&2
  exit 1
fi

echo "[3/4] 快进 main 并推送到 fork ..."
git checkout "$MAIN"
git merge --ff-only "$UPSTREAM/$MAIN"
git push "$ORIGIN" "$MAIN"

echo "[4/4] 完成。适配分支请手动合并："
echo "  git checkout codebuddy-cli-adapt && git merge $MAIN"
echo "下一步：按 ADAPTATION.md 的 tag 规范打 annotated tag 并推送。"

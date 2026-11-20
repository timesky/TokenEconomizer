"""Runtime injection of CodeBuddy support into the upstream TokenEconomizer package.

Nothing in ``tokeneconomizer/`` is edited. This module is imported by the CodeBuddy launcher
before the upstream hook/CLI entry point runs, and patches only in-memory registries:

  1. ``hosts.HOSTS["codebuddy"]``            -- makes ``--host codebuddy`` valid;
  2. ``hosts.detect``                        -- recognises CodeBuddy hook payloads;
  3. ``hosts.default_host``                  -- picks codebuddy inside a CodeBuddy shell;
  4. ``config._ENV`` paid-model whitelist   -- enables TE_CODEBUDDY_PAID_MODEL;
  5. ``history.HOST_LABEL``                  -- human-readable host label.

The patch is idempotent: calling install() twice is a no-op. If a future upstream release
renames any of these attributes, install() degrades safely (it records what it could not wire
and leaves the rest of the plugin unchanged) rather than raising into a hook.
"""
import os

_INSTALLED = False
_WARNINGS = []


def warnings():
    return list(_WARNINGS)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from tokeneconomizer.plugin import hosts, config

    # 1 + 2: host class + detection.
    from .host import CodeBuddy
    hosts.HOSTS["codebuddy"] = CodeBuddy

    original_detect = hosts.detect

    def detect(payload, env=None, hint=None):
        if hint == "codebuddy":
            return CodeBuddy()
        if hint in hosts.HOSTS and hint is not None:
            return hosts.HOSTS[hint]()
        p = payload or {}
        tp = str(p.get("transcript_path") or "").replace("\\", "/")
        env = env if env is not None else os.environ
        # A CodeBuddy transcript lives under <config>/projects/<slug>/<sid>.jsonl; its hook
        # processes also carry CODEBUDDY_PLUGIN_ROOT. The transcript test comes first so a
        # CodeBuddy session started from inside another agent is still read as CodeBuddy.
        if "/.codebuddy/projects/" in tp:
            return CodeBuddy()
        if not tp and (env.get("CODEBUDDY_PLUGIN_ROOT") or env.get("CODEBUDDY_CONFIG_DIR")):
            return CodeBuddy()
        return original_detect(payload, env, hint=hint)

    hosts.detect = detect

    # 3: default host for `te` commands run in a CodeBuddy shell.
    original_default = hosts.default_host

    def default_host(env=None, recent=None):
        env = env if env is not None else os.environ
        if env.get("TE_HOST") == "codebuddy":
            return "codebuddy"
        if env.get("CODEBUDDY_PLUGIN_ROOT") or env.get("CODEBUDDY_SESSION_ID"):
            return "codebuddy"
        return original_default(env=env, recent=recent)

    hosts.default_host = default_host

    # 4: per-host paid-model override (TE_CODEBUDDY_PAID_MODEL).
    try:
        config._ENV["TE_CODEBUDDY_PAID_MODEL"] = "codebuddy_paid_model"
    except (AttributeError, TypeError):
        _WARNINGS.append("config._ENV not patchable; TE_CODEBUDDY_PAID_MODEL unavailable")

    # 5: host label in reports/history.
    try:
        from tokeneconomizer.plugin import history
        history.HOST_LABEL["codebuddy"] = "CodeBuddy CLI"
    except (ImportError, AttributeError, TypeError):
        _WARNINGS.append("history.HOST_LABEL not patchable; label will read 'codebuddy'")

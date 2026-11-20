"""CodeBuddy launcher: inject the CodeBuddy add-on, then run the upstream entry point.

The upstream `te_bootstrap.py` locates the core package and dispatches to `hook.main` or
`cli.main`, but imports them itself before any add-on can register. This launcher repeats the
same core-location step, installs the shim first, and then calls the upstream entry point. The
upstream files are never edited.

Kept importable by any Python 3 (like te_bootstrap.py): no f-strings, no annotations, nothing
newer than 3.0, so an old interpreter can still answer a hook with `{}`.
"""
import os
import sys

MIN_VERSION = (3, 10)


def _plugin_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _addon_root(core=None):
    """Find the directory that holds the `codebuddy` shim package.

    CodeBuddy marketplace installs copy only `plugin/` into
    ~/.codebuddy/plugins/cache/<market>/<plugin>/<version>, so the clone-root
    `codebuddy/` package is not copied alongside. The upstream core_path() still
    resolves to the original clone (via known_marketplaces.json), and that clone
    holds the shim, so prefer `core` when it is available. Fall back to the
    plugin's parent (direct clone) and then to the plugin dir itself.
    """
    seen = []
    for cand in (core, os.path.dirname(_plugin_root()), _plugin_root()):
        if cand and cand not in seen:
            seen.append(cand)
    # CodeBuddy copies the lib symlink as a real directory, so core often resolves
    # inside the cache and no longer points at the clone. Recover the clone from
    # the marketplace source recorded by CodeBuddy (same source the upstream core
    # discovery uses) and include it as a candidate for the shim package.
    try:
        import te_bootstrap
        for cand in te_bootstrap._marketplace_sources(_plugin_root()):
            if cand and cand not in seen:
                seen.append(cand)
    except (ImportError, AttributeError):
        pass
    for cand in seen:
        if os.path.isfile(os.path.join(cand, "codebuddy", "shim.py")):
            return cand
    # Nothing matched: keep the historical default so callers still behave.
    return os.path.dirname(_plugin_root())


def _core_path():
    """Same discovery order as te_bootstrap.core_path(), plus TE_CORE_PATH first."""
    sys.path.insert(0, os.path.join(_plugin_root(), "scripts"))
    try:
        import te_bootstrap
        return te_bootstrap.core_path()
    except (ImportError, AttributeError):
        pass
    root = _plugin_root()
    for cand in (os.environ.get("TE_CORE_PATH"), os.path.join(root, "lib"),
                 os.path.dirname(root)):
        if cand and os.path.isfile(os.path.join(cand, "tokeneconomizer", "plugin", "hook.py")):
            return cand
    return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "hook"
    rest = sys.argv[2:]
    if sys.version_info < MIN_VERSION:
        if mode == "hook":
            getattr(sys.stdin, "buffer", sys.stdin).read()
            sys.stdout.write("{}\n")
            return 0
        sys.stderr.write("TokenEconomizer needs Python >= %d.%d (this is %s); set TE_PYTHON\n"
                         % (MIN_VERSION[0], MIN_VERSION[1], sys.version.split()[0]))
        return 1

    os.umask(0o077)
    os.environ["TE_PLUGIN_ROOT"] = _plugin_root()
    core = _core_path()
    if core:
        sys.path.insert(0, core)
    addon_root = _addon_root(core)
    if addon_root not in sys.path:
        sys.path.insert(0, addon_root)

    try:
        from codebuddy.shim import install
        install()
        from tokeneconomizer.plugin import hook, cli
        if mode == "hook":
            return hook.main(rest)
        return cli.main(rest)
    except ImportError:
        if mode == "hook":
            sys.stdout.write("{}\n")
            return 0
        raise


if __name__ == "__main__":
    sys.exit(main())

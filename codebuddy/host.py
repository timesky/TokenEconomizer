"""CodeBuddy CLI host adapter (add-on, no edits to the upstream package).

Subclasses the upstream ``Host`` contract and points its session-reading methods at
``codebuddy.trace``. Registered into ``hosts.HOSTS`` by ``codebuddy.shim.install()``.

Mechanism support (matches what the CodeBuddy host contract actually verifies):
  * micro-skills       -- on: facts are injected at SessionStart / UserPromptSubmit and a
                          finished session's Claude-shaped trace is folded;
  * loop guard         -- on: prompt-turn context reaches the model;
  * tool pruning       -- off: no verified deny-rule interface for CodeBuddy settings, so the
                          host does not claim support (same stance as Cursor/Grok/Antigravity).

All learned state is namespaced under host name "codebuddy", isolated from Claude Code.
"""
import os

from tokeneconomizer.plugin import hosts as _hosts
from tokeneconomizer import trace as _trace
from . import trace as _cb_trace

Host = _hosts.Host


class CodeBuddy(Host):
    name = "codebuddy"
    prompt_context = True       # UserPromptSubmit additionalContext reaches the model (verified)
    relays_notices = True       # hook messages are not shown where the user looks -> relay them
    keeps_start_context = True

    interrupt = "Press Esc to stop the CodeBuddy agent."
    end_run = "Press Ctrl+C to end the CodeBuddy CLI run."

    def session_id(self, p):
        return str(p.get("session_id") or p.get("conversation_id") or "")

    def cwd(self, p, env):
        return (p.get("cwd") or env.get("CODEBUDDY_PROJECT_DIR") or
                env.get("CLAUDE_PROJECT_DIR") or os.getcwd())

    def env_session_id(self, env):
        return str(env.get("TE_SESSION_ID") or env.get("CODEBUDDY_SESSION_ID") or "")

    def turn_key(self, p):
        # CodeBuddy marks a request with conversationRequestId; fall back to prompt_id.
        return str(p.get("conversationRequestId") or p.get("prompt_id") or "")

    def tool_call(self, p):
        name, args, text, code = super().tool_call(p)
        # CodeBuddy's hook tool names can be OpenAI-style; fold the common ones onto the
        # vocabulary the mechanisms already classify (SHELL_TOOLS, TOOL_ROLES).
        low = name.lower()
        if low in ("shell", "exec_command", "local_shell", "bash"):
            return "Bash", args, text, code
        if low in ("functions.read", "read_file"):
            return "Read", args, text, code
        if low in ("functions.edit", "str_replace", "functions.write", "write_file"):
            return "Edit", args, text, code
        return name, args, text, code

    # -- finished session ---------------------------------------------------------------
    def mechanism_trace(self, transcript_path, workdir):
        out = os.path.join(workdir, "codebuddy_trace.jsonl")
        n = _cb_trace.session_to_claude(transcript_path, out)
        return out if n is not None else None

    def session_usage(self, transcript_path):
        return _cb_trace.session_usage(transcript_path)

    def prompt_count(self, transcript_path):
        return _cb_trace.session_prompt_count(transcript_path)

    def tool_usage(self, trace_path):
        return _cb_trace.session_tool_usage(trace_path)

    # Host defines keeps_history as a class attribute; set it so history() is consulted.
    keeps_history = True

    def history(self, env, extra_dirs=()):
        """CodeBuddy session logs under ~/.codebuddy/projects (or CODEBUDDY_CONFIG_DIR)."""
        root = env.get("CODEBUDDY_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".codebuddy")
        base = os.path.join(root, "projects")
        dirs = [base]
        for d in extra_dirs or ():
            p = os.path.expanduser(str(d))
            dirs.append(os.path.join(p, "projects") if os.path.isdir(os.path.join(p, "projects"))
                        else p)
        out, seen, seen_dirs = [], set(), set()
        for d in dirs:
            real = os.path.realpath(d)
            if real in seen_dirs:
                continue
            seen_dirs.add(real)
            if not os.path.isdir(d):
                continue
            for name in os.listdir(d):
                folder = os.path.join(d, name)
                if not os.path.isdir(folder):
                    continue
                for fname in os.listdir(folder):
                    if not fname.endswith(".jsonl"):
                        continue
                    path = os.path.join(folder, fname)
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    sid = fname[:-len(".jsonl")]
                    if sid in seen:
                        continue
                    seen.add(sid)
                    out.append({"session_id": sid, "folder": name, "path": path,
                                "mtime": st.st_mtime, "size": st.st_size})
        return out

    def safe_session_id(self, sid):
        return _trace.claude_safe_session_id(sid)

    def log_head(self, path):
        return _trace.claude_log_head(path)

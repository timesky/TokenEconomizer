"""Offline tests for the CodeBuddy CLI add-on.

Run:  PYTHONPATH=. python -m pytest tests/test_codebuddy_adapter.py -q
No network, no CodeBuddy install, no edits to the user's plugin directory. Uses hand-built
fixtures that mirror the real CodeBuddy transcript shape verified on 2026-11-20.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codebuddy import trace as t  # noqa: E402


def _event(**kw):
    kw.setdefault("sessionId", "sess-1")
    kw.setdefault("cwd", "/repo")
    return kw


def _write(tmp_path, events, name="session.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
                    encoding="utf-8")
    return str(path)


def _usage(**overrides):
    raw = {"cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
           "prompt_cache_hit_tokens": 300, "prompt_cache_miss_tokens": 50,
           "prompt_cache_write_tokens": 10, "completion_tokens": 20,
           "prompt_tokens": 350}
    raw.update(overrides)
    return {"providerData": {"messageId": "m1", "rawUsage": raw,
                             "requestModelName": "Test-Model"}}


# --- transcript -> Claude-shaped trace ---------------------------------------------------
def test_session_to_claude_shapes(tmp_path):
    events = [
        _event(type="message", role="user",
               content=[{"type": "input_text", "text": "do a thing"}]),
        _event(type="function_call", name="Bash", call_id="c1",
               arguments={"command": "ls"}, providerData=_usage()["providerData"]),
        _event(type="function_call_result", call_id="c1", name="Bash",
               status="completed", output={"type": "text", "text": "ok"}),
        _event(type="message", role="assistant",
               content=[{"type": "output_text", "text": "done"}]),
    ]
    out = str(tmp_path / "trace.jsonl")
    assert t.session_to_claude(_write(tmp_path, events), out) == 4
    rows = [json.loads(l) for l in open(out, encoding="utf-8")]
    assert rows[0]["type"] == "user"
    assert rows[0]["message"]["content"][0] == {"type": "text", "text": "do a thing"}
    assert rows[1]["message"]["content"][0]["type"] == "tool_use"
    assert rows[2]["message"]["content"][0]["type"] == "tool_result"
    assert rows[2]["message"]["content"][0]["content"][0]["text"] == "ok"
    assert rows[3]["type"] == "assistant"


def test_session_to_claude_upstream_reader(tmp_path):
    """The converted trace must be readable by the untouched upstream load_trajectory."""
    from tokeneconomizer import trace as upstream
    events = [
        _event(type="message", role="user", content=[{"type": "input_text", "text": "go"}]),
        _event(type="function_call", name="Bash", call_id="c1", arguments={"command": "ls"}),
        _event(type="function_call_result", call_id="c1", status="completed",
               output={"type": "text", "text": "a"}),
    ]
    out = str(tmp_path / "trace.jsonl")
    t.session_to_claude(_write(tmp_path, events), out)
    traj = upstream.load_trajectory(out)
    assert len(traj) == 1
    assert traj[0][0] == "Bash"
    assert traj[0][3] is True


def test_tool_result_failure_marks_error(tmp_path):
    events = [
        _event(type="function_call", name="Bash", call_id="c1", arguments={}),
        _event(type="function_call_result", call_id="c1", status="failed",
               output={"type": "text", "text": "boom"}),
    ]
    out = str(tmp_path / "trace.jsonl")
    t.session_to_claude(_write(tmp_path, events), out)
    rows = [json.loads(l) for l in open(out, encoding="utf-8")]
    assert rows[1]["message"]["content"][0]["is_error"] is True


def test_unreadable_returns_none(tmp_path):
    assert t.session_to_claude(str(tmp_path / "nope.jsonl"), str(tmp_path / "out.jsonl")) is None


# --- usage + counts ----------------------------------------------------------------------
def test_usage_prefers_openai_cache_names(tmp_path):
    path = _write(tmp_path, [_usage()])
    u = t.session_usage(path)
    assert u["input_tokens"] == 50
    assert u["cache_read_input_tokens"] == 300      # not the zero placeholder
    assert u["cache_creation_input_tokens"] == 10   # not the zero placeholder
    assert u["output_tokens"] == 20
    assert u["requests"] == 1
    assert u["model"] == "Test-Model"


def test_usage_dedup_by_message_id(tmp_path):
    path = _write(tmp_path, [_usage(), _usage()])  # same messageId -> last wins, counted once
    assert t.session_usage(path)["requests"] == 1


def test_prompt_count_excludes_tool_results(tmp_path):
    events = [
        _event(type="message", role="user", content=[{"type": "input_text", "text": "hi"}]),
        _event(type="function_call_result", call_id="c1", output={"type": "text", "text": "x"}),
        _event(type="message", role="assistant", content=[{"type": "output_text", "text": "yo"}]),
    ]
    assert t.session_prompt_count(_write(tmp_path, events)) == 1


def test_tool_usage_counts_calls(tmp_path):
    events = [
        _event(type="function_call", name="Bash", call_id="c1", arguments={}),
        _event(type="function_call", name="Read", call_id="c2", arguments={}),
        _event(type="function_call", name="Bash", call_id="c3", arguments={}),
    ]
    assert t.session_tool_usage(_write(tmp_path, events)) == {"Bash": 2, "Read": 1}


# --- shim injection ----------------------------------------------------------------------
def test_shim_registers_codebuddy_without_touching_upstream():
    from codebuddy.shim import install
    install()
    from tokeneconomizer.plugin import hosts, config, history
    assert "codebuddy" in hosts.HOSTS
    assert hosts.detect({}, {}, hint="codebuddy").name == "codebuddy"
    assert hosts.detect({"transcript_path": "/x/.codebuddy/projects/p/s.jsonl"}, {}).name == "codebuddy"
    assert hosts.detect({"transcript_path": "/x/.claude/projects/p/s.jsonl"}, {}).name == "claude"
    assert config._ENV.get("TE_CODEBUDDY_PAID_MODEL") == "codebuddy_paid_model"
    assert history.HOST_LABEL.get("codebuddy") == "CodeBuddy CLI"

"""CodeBuddy CLI transcript reader (add-on, no edits to the upstream package).

CodeBuddy writes JSONL under ``~/.codebuddy/projects/<project>/<session>.jsonl`` and reuses a
large part of the Anthropic envelope, with differences the upstream ``trace.claude`` reader
does not understand:

  * conversation rows have ``type: "message"`` with ``role``/``content`` at the top level
    (not ``type: "assistant"``/``"user"`` with a nested ``message`` object);
  * text blocks are ``input_text`` / ``output_text`` (not ``text``);
  * tool calls are standalone ``function_call`` rows answered by ``function_call_result``
    rows (not ``tool_use`` / ``tool_result`` blocks inside a message);
  * per-request usage lives in ``providerData.rawUsage`` on the function-call/reasoning
    rows, in OpenAI-style token names.

The functions here produce two things the rest of TokenEconomizer already knows how to read:

  * ``session_to_claude`` -- a Claude-shaped JSONL trajectory for the mechanism layer;
  * ``session_usage`` / ``session_prompt_count`` -- cost and prompt count from the raw log.

Everything is standard library only. A row the reader does not recognise is skipped, never
guessed at: an unreadable session is reported as empty rather than folded from wrong evidence.
"""
import json
import os

_TEXT_TYPES = ("text", "input_text", "output_text")
_CALL_TYPES = ("function_call", "tool_call")
_RESULT_TYPES = ("function_call_result", "function_call_output", "tool_result")
_CONVERSATION = ("message", "user", "assistant")

# OpenAI-style rawUsage -> the four fields pricing.effective_tokens reads.
#
# CodeBuddy writes BOTH a zero-valued Anthropic-named field (cache_read_input_tokens,
# cache_creation_input_tokens) and the real count under OpenAI names
# (prompt_cache_hit_tokens, prompt_cache_write_tokens). The zeros are placeholders, so the
# OpenAI name must win here. The real fields are listed first deliberately.
_USAGE_KEYS = {
    "input_tokens": ("prompt_cache_miss_tokens", "input_tokens"),
    "cache_read_input_tokens": ("prompt_cache_hit_tokens", "cached_tokens",
                                "cache_read_input_tokens"),
    "cache_creation_input_tokens": ("prompt_cache_write_tokens", "cache_creation_input_tokens"),
    "output_tokens": ("completion_tokens", "output_tokens"),
}
# Kept for callers that want to know which names were consulted; not used for the sum.
_PLACEHOLDER_FIELDS = ("cache_read_input_tokens", "cache_creation_input_tokens")


def _lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield line


def _loads(line):
    try:
        ev = json.loads(line)
    except (ValueError, TypeError):
        return None
    return ev if isinstance(ev, dict) else None


def _block_text(block):
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return ""
    text = block.get("text")
    if isinstance(text, str):
        return text
    for key in ("content", "output", "result"):
        value = block.get(key)
        if isinstance(value, str):
            return value
    return ""


def _content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_block_text(b) for b in content if _block_text(b))
    return _block_text(content)


def _call_info(event):
    """(call_id, name, args) for a function_call row, or None."""
    if event.get("type") not in _CALL_TYPES:
        return None
    call_id = str(event.get("call_id") or event.get("id") or "")
    fn = event.get("function") if isinstance(event.get("function"), dict) else {}
    name = event.get("name") or fn.get("name") or event.get("tool_name") or "unknown"
    args = event.get("arguments")
    if args is None:
        args = event.get("input")
    if args is None:
        args = fn.get("arguments")
    if not isinstance(args, (dict, list, str)):
        args = {}
    return call_id, str(name), args


def _result_info(event):
    """(call_id, output_text, ok) for a function_call_result row, or None."""
    if event.get("type") not in _RESULT_TYPES:
        return None
    call_id = str(event.get("call_id") or event.get("tool_call_id") or
                  event.get("parentId") or event.get("id") or "")
    out = event.get("output")
    if out is None:
        out = event.get("content")
    if out is None:
        out = event.get("result")
    ok = str(event.get("status") or "").lower() not in ("error", "failed", "failure")
    if event.get("is_error") or event.get("error"):
        ok = False
    return call_id, _content_text(out), ok


def session_to_claude(path, out_path):
    """Write a Claude-shaped trajectory from a CodeBuddy session. Return row count or None.

    Shapes emitted (all read by the upstream ``trace`` package):

      * ``{"type":"user","message":{"content":[{"type":"text","text":...}]}}`` for prompts;
      * ``{"type":"assistant","message":{"content":[{"type":"tool_use",...}]}}`` for calls;
      * ``{"type":"user","message":{"content":[{"type":"tool_result",...}]}}`` for results;
      * a final assistant text row when the turn ended with an answer (loop guard).

    ``cwd`` is kept on rows so ``claude_calls`` can attribute shell commands to a directory.
    """
    try:
        events = [_loads(line) for line in _lines(path)]
    except OSError:
        return None
    events = [e for e in events if e is not None]
    if not events:
        return None

    out = []
    for ev in events:
        cwd = ev.get("cwd") if isinstance(ev.get("cwd"), str) else None
        etype = ev.get("type")

        if etype in _CONVERSATION:
            role = ev.get("role") or ("assistant" if etype == "assistant" else "user")
            content = ev.get("content")
            blocks = []
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") in _TEXT_TYPES:
                        text = _block_text(b)
                        if text:
                            blocks.append({"type": "text", "text": text})
            elif isinstance(content, str) and content.strip():
                blocks.append({"type": "text", "text": content})
            if not blocks:
                continue
            row = {"type": "assistant" if role == "assistant" else "user",
                   "message": {"content": blocks}}
            if cwd:
                row["cwd"] = cwd
            out.append(row)
            continue

        call = _call_info(ev)
        if call:
            call_id, name, args = call
            row = {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": call_id, "name": name, "input": args}]}}
            if cwd:
                row["cwd"] = cwd
            out.append(row)
            continue

        result = _result_info(ev)
        if result:
            call_id, text, ok = result
            content = [{"type": "text", "text": text}] if text else []
            row = {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": call_id,
                 "content": content, "is_error": not ok}]}}
            if cwd:
                row["cwd"] = cwd
            out.append(row)

    if not out:
        return None
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(out)


def _usage_of(event):
    provider = event.get("providerData")
    if not isinstance(provider, dict):
        return None
    raw = provider.get("rawUsage")
    return raw if isinstance(raw, dict) else None


def _first_int(raw, keys):
    for key in keys:
        if key in raw and raw[key] is not None:
            try:
                return int(raw[key])
            except (TypeError, ValueError):
                continue
    return None


def session_usage(path):
    """Token breakdown in the shape ``pricing.effective_tokens`` reads.

    CodeBuddy writes one usage record per model request, deduplicated by ``messageId``; later
    rows for the same request carry the final counts, so the last one wins (same rule as the
    upstream Claude reader). Requests with no usage record are not counted.
    """
    by_id, anon, models = {}, 0, {}
    for line in _lines(path):
        ev = _loads(line)
        if not ev:
            continue
        raw = _usage_of(ev)
        if not raw:
            continue
        provider = ev["providerData"]
        mid = str(provider.get("messageId") or "")
        if not mid:
            anon += 1
            mid = "anon-%d" % anon
        rec = {}
        for field, keys in _USAGE_KEYS.items():
            value = _first_int(raw, keys)
            if value is None:
                continue
            rec[field] = value
        if not rec:
            continue
        by_id[mid] = rec
        model = provider.get("requestModelName") or provider.get("model")
        if model:
            models[str(model)] = models.get(str(model), 0) + 1
    out = {k: sum(r.get(k, 0) for r in by_id.values()) for k in _USAGE_KEYS}
    out["cache_creation_1h_input_tokens"] = 0
    out["requests"] = len(by_id)
    out["model"] = max(models, key=models.get) if models else None
    out["files"] = 1 if os.path.exists(path) else 0
    return out


def session_prompt_count(path):
    """Prompts the person submitted: ``message`` rows with role ``user``, not tool results."""
    count = 0
    for line in _lines(path):
        ev = _loads(line)
        if not ev or ev.get("type") not in _CONVERSATION:
            continue
        if str(ev.get("role") or "").lower() == "user":
            count += 1
    return count


def session_tool_usage(path):
    """{tool_name: calls} from the function_call rows of a session."""
    counts = {}
    for line in _lines(path):
        ev = _loads(line)
        if not ev:
            continue
        call = _call_info(ev)
        if call:
            counts[call[1]] = counts.get(call[1], 0) + 1
    return counts

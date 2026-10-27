"""Helpers for Responses API items (input and output), which may be dicts or SDK objects."""

SUMMARY_TAG = "conversation_summary"


def get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def plain(item):
    """An item as a JSON-serializable dict that can be sent back as input."""
    if isinstance(item, dict):
        return item
    return item.model_dump(exclude_none=True)


def kind(item):
    return get(item, "type") or "message"


def user_item(text):
    return {"role": "user", "content": text}


def summary_item(text):
    return user_item(f"<{SUMMARY_TAG}>\n{text}\n</{SUMMARY_TAG}>")


def is_summary(item):
    return kind(item) == "message" and str(get(item, "content", "")).startswith(f"<{SUMMARY_TAG}>")


def is_user_turn(item):
    """True for the message that starts a user turn (not a compaction summary)."""
    return kind(item) == "message" and get(item, "role") == "user" and not is_summary(item)


def function_calls(output):
    return [i for i in output if kind(i) == "function_call"]


def call_output_item(call_id, text):
    return {"type": "function_call_output", "call_id": call_id, "output": text}


def output_text(output):
    """The assistant's visible text from a response output list."""
    parts = []
    for item in output:
        if kind(item) == "message" and get(item, "role", "assistant") == "assistant":
            content = get(item, "content") or []
            parts += [get(c, "text", "") for c in content if get(c, "type") == "output_text"]
    return "".join(parts)

"""JobScout on the Codex SDK (ChatGPT login). Codex runs the loop; this file only configures it."""
import json
from pathlib import Path

from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox

from shared import pricing, prompts
from shared.store import Store
from SDK import tools as sdk_tools

ZERO = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "cache_write_input_tokens": 0}


def load_session(state_dir):
    p = Path(state_dir) / "sdk_session.json"
    return json.loads(p.read_text()) if p.exists() else None


def save_session(state_dir, thread_id, total):
    (Path(state_dir) / "sdk_session.json").write_text(json.dumps({"thread_id": thread_id, "total": total}))


class JobScoutSDKAgent:
    def __init__(self, state_dir, session, model, effort, http_mode):
        self.state_dir, self.session, self.model = Path(state_dir), session, model
        self.store = Store(state_dir)
        # memory + context: a short AGENTS.md that Codex loads from its working directory
        (self.state_dir / "AGENTS.md").write_text(_memory_markdown(self.store))  # replaces: memory, context
        self.codex = Codex(CodexConfig(  # replaces: loop
            cwd=str(self.state_dir.resolve()),  # replaces: memory
            config_overrides=sdk_tools.config_overrides(state_dir, http_mode, effort)))  # replaces: tools
        options = dict(
            model=model,  # same model as the API version
            developer_instructions=prompts.SYSTEM_PROMPT,  # replaces: context  (my own system prompt)
            cwd=str(self.state_dir.resolve()),  # replaces: memory
            sandbox=Sandbox.read_only,  # replaces: tools  (no file writes)
            approval_mode=ApprovalMode.deny_all,  # replaces: tools  (nothing outside the MCP tools can run)
        )
        saved = load_session(state_dir)
        if saved:  # session 2: continue the saved thread
            self.thread = self.codex.thread_resume(saved["thread_id"], **options)  # replaces: history
            self.prev_total = saved["total"]
        else:
            self.thread = self.codex.thread_start(**options)  # replaces: history
            self.prev_total = dict(ZERO)
        save_session(state_dir, self.thread.id, self.prev_total)  # replaces: history

    def ask(self, text):
        result = self.thread.run(text)  # replaces: loop
        total = _breakdown(result.usage.total) if result.usage else self.prev_total  # replaces: tokens
        delta = {k: total[k] - self.prev_total[k] for k in ZERO}  # replaces: tokens
        self.prev_total = total
        save_session(self.state_dir, self.thread.id, total)  # replaces: history
        tokens = {"input": delta["input_tokens"] - delta["cached_input_tokens"],  # replaces: tokens
                  "cache_read": delta["cached_input_tokens"],
                  "cache_write": delta["cache_write_input_tokens"],
                  "output": delta["output_tokens"]}
        # tools come from the shared tool log (written by the MCP server), not from SDK item shapes
        tools = [e["tool"] for e in self.store.read_jsonl("tool_log.jsonl")
                 if e.get("turn") == self.store.current_turn()]
        return {
            "answer": result.final_response or "",
            "tokens": tokens,
            "model_calls": len(tools) + 1,  # Codex does not report this: one per tool round + the final answer
            "tools": tools,
            "cost_usd": pricing.cost_usd(self.model, delta["input_tokens"], delta["cached_input_tokens"],
                                         delta["output_tokens"]),  # replaces: tokens
            "time_s": round((result.duration_ms or 0) / 1000, 2),
        }

    def end_session(self):
        self.codex.close()
        # compaction + caching: automatic in Codex  # replaces: compaction, caching


def _breakdown(b):
    return {k: getattr(b, k, 0) or 0 for k in ZERO}


def _memory_markdown(store):
    """What JobScout remembers, as short Markdown (the SDK's version of memory + context)."""
    p = store.profile()
    return ("# JobScout memory\n\n"
            f"- roles: {p['roles']}\n- cities: {p['cities']}\n- strict_cities: {p['strict_cities']}\n"
            f"- skip_companies: {p['skip_companies']}\n- {store.tracker_summary()}\n\n"
            "Use get_tracker / get_profile for anything more.\n")

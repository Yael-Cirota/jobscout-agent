"""Tool schemas for the Responses API, and dispatch of the model's function calls."""
import json

from shared import tool_specs, tools_impl

from . import items
from .logger import log


def schemas(specs=None):
    """Function-tool definitions built from the shared specs (the single source of truth)."""
    return [{"type": "function", "name": name, "description": spec["description"],
             "parameters": spec["input_schema"], "strict": False}
            for name, spec in (specs or tool_specs.SPECS).items()]


class ToolExecutor:
    """Runs one function_call item and returns its function_call_output item. Never raises.

    OpenAI has no `is_error` flag, so a failure is reported inside the output JSON instead.
    """

    def __init__(self, store, runner=tools_impl.run_tool):
        self.store, self.runner = store, runner

    def run(self, call):
        name, call_id = items.get(call, "name"), items.get(call, "call_id")
        raw = items.get(call, "arguments")
        args, problem = self._parse(raw)
        if problem:
            self.store.log_tool({"tool": name, "args": None, "ok": False, "chars": len(problem), "error": problem})
            result = {"ok": False, "text": problem}
        else:
            result = self.runner(self.store, name, args)
        output = result["text"] if result["ok"] else json.dumps({"error": result["text"], "is_error": True})
        log(__file__, f"{name}({raw or '{}'}) -> {'ok' if result['ok'] else 'error'}, {len(output)} chars")
        return items.call_output_item(call_id, output)

    @staticmethod
    def _parse(raw):
        try:
            args = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return None, "Arguments are not valid JSON."
        if not isinstance(args, dict):
            return None, "Arguments must be a JSON object."
        return args, None

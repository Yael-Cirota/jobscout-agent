"""$ per million tokens. Fill from the official OpenAI pricing page when you build,
and write the date next to the numbers. Unknown model -> cost is None (never a guess).

PRICES = {"<model>": {"input": .., "cached_input": .., "output": ..}}
"""
PRICES_DATE = None  # e.g. "2026-10-25" - set when you fill PRICES
PRICES = {}


def cost_usd(model, input_tokens, cached_tokens, output_tokens):
    """input_tokens includes cached_tokens (OpenAI convention)."""
    p = PRICES.get(model)
    if not p:
        return None
    uncached = max(input_tokens - cached_tokens, 0)
    return round((uncached * p["input"] + cached_tokens * p["cached_input"]
                  + output_tokens * p["output"]) / 1_000_000, 6)

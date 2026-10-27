"""$ per million tokens. Fill from the official OpenAI pricing page when you build,
and write the date next to the numbers. Unknown model -> cost is None (never a guess).

PRICES = {"<model>": {"input": .., "cached_input": .., "output": ..}}
"""
PRICES_DATE = "2026-10-28"  # from public aggregators (OpenRouter, Requesty, ...); not checked on openai.com
PRICES = {"gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20}}  # short-context tier


def cost_usd(model, input_tokens, cached_tokens, output_tokens):
    """input_tokens includes cached_tokens (OpenAI convention)."""
    p = PRICES.get(model)
    if not p:
        return None
    uncached = max(input_tokens - cached_tokens, 0)
    return round((uncached * p["input"] + cached_tokens * p["cached_input"]
                  + output_tokens * p["output"]) / 1_000_000, 6)

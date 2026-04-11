# Harga per juta token (USD) — update di sini jika ada perubahan harga
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6":    {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6":  {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5":   {"input": 0.8,   "output": 4.0},
    "copilot-gpt4o":      {"input": 5.0,   "output": 15.0},
    "copilot-gpt4":       {"input": 10.0,  "output": 30.0},
}

DEFAULT_RATES = {"input": 3.0, "output": 15.0}


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model, DEFAULT_RATES)
    return (
        (input_tokens / 1_000_000) * rates["input"] +
        (output_tokens / 1_000_000) * rates["output"]
    )

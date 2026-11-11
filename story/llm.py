from collections import Counter

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

MODEL = "claude-haiku-5-5"
PRICE_PER_MTOK = {"input": 0.10, "output": 0.50}  # Haiku 5.5, prompts under 100K tokens
client = anthropic.Anthropic()
usage = Counter()  # process-wide token totals, read by evals


def cost_usd() -> float:
    return sum(usage[k] * p for k, p in PRICE_PER_MTOK.items()) / 1e6


class LLMError(RuntimeError):
    pass


def _check_complete(resp) -> None:
    usage.update(input=resp.usage.input_tokens, output=resp.usage.output_tokens, calls=1)
    # Only a normal finish counts; refusal, max_tokens, or anything unexpected is incomplete.
    if resp.stop_reason != "end_turn":
        raise LLMError(f"Incomplete response: {resp.stop_reason} (request {resp._request_id})")


def call_model(prompt: str, system: str, max_tokens: int = 16000, on_text=None) -> str:
    """Return the model's text. With `on_text`, stream it and call on_text(chunk) as words arrive."""
    kwargs = dict(model=MODEL, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": prompt}])
    if on_text:
        with client.messages.stream(**kwargs) as stream:
            for chunk in stream.text_stream:
                on_text(chunk)
            resp = stream.get_final_message()
    else:
        resp = client.messages.create(**kwargs)
    _check_complete(resp)
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not text:
        raise LLMError(f"Empty response (request {resp._request_id})")
    return text


def call_structured[T: BaseModel](prompt: str, schema: type[T], system: str, max_tokens: int = 16000) -> T:
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
    )
    _check_complete(resp)
    if resp.parsed_output is None:
        raise LLMError(f"No structured output (request {resp._request_id})")
    return resp.parsed_output

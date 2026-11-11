import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

MODEL = "claude-haiku-5-5"
client = anthropic.Anthropic()


def call_model(prompt: str, system: str | None = None, max_tokens: int = 16000) -> str:
    kwargs = {"system": system} if system else {}
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Model refused (request {resp._request_id})")
    return "".join(b.text for b in resp.content if b.type == "text")


def call_structured[T: BaseModel](prompt: str, schema: type[T], system: str, max_tokens: int = 16000) -> T:
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise RuntimeError(f"No structured output: {resp.stop_reason} (request {resp._request_id})")
    return resp.parsed_output

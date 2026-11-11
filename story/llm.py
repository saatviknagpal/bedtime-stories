import anthropic
from dotenv import load_dotenv

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

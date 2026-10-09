"""Smoke test: check that the Anthropic API key and model are working.

    python main.py
"""

from anthropic import Anthropic

from config import MODEL

client = Anthropic()

response = client.messages.create(
    model=MODEL,
    max_tokens=200,
    messages=[{"role": "user", "content": "Reply with one short sentence to say hello."}],
)

print(response.content[0].text)

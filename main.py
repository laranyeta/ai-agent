from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

respuesta = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
    messages=[{"role": "user", "content": "Saluda en una frase."}],
)
print(respuesta.content[0].text)

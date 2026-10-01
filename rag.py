import chromadb
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

client_claude = Anthropic()
client_chroma = chromadb.PersistentClient(path="./chroma_db")
collection = client_chroma.get_or_create_collection(name="my_docs")

def get_context(query: str, n_results: int = 3) -> str:
    res = collection.query(query_texts=[query], n_results=n_results)
    fragments = res["documents"][0]
    return "\n\n---\n\n".join(fragments)

def ask(query: str) -> str:
    context = get_context(query)
    response = client_claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Usa este contexto para responder la pregunta.\n\nContexto:\n{context}\n\nPregunta: {pregunta}",
        }],
    )
    return response.content[0].text

if __name__ == "__main__":
    pregunta = "¿Qué tecnologías se repiten más en las ofertas guardadas?"
    print(ask(pregunta))

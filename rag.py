"""Minimal RAG over the indexed CV, with no MCP and no tools.

This is the retrieval layer on its own: retrieve, stuff, answer. It is kept
as a reference and as a quick way to check that indexing and retrieval work
before bringing the agent and its tools into the picture.

    python rag.py
"""

from anthropic import Anthropic

from config import MAX_TOKENS, MODEL, N_RESULTS, get_collection

client_claude = Anthropic()
collection = get_collection()

SYSTEM_PROMPT = (
    "Answer the question using only the context provided. "
    "If the answer is not in the context, say so instead of guessing."
)


def get_context(query: str, n_results: int = N_RESULTS) -> str:
    """Return the indexed chunks most similar to the query."""
    results = collection.query(query_texts=[query], n_results=n_results)
    documents = results.get("documents") or [[]]
    fragments = documents[0]
    if not fragments:
        return "No documents have been indexed yet. Run: python index.py"
    return "\n\n---\n\n".join(fragments)


def ask(query: str) -> str:
    """Answer one question from the indexed documents."""
    context = get_context(query)
    response = client_claude.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            }
        ],
    )
    return response.content[0].text


if __name__ == "__main__":
    question = "What is my experience with machine learning in production?"
    print(ask(question))

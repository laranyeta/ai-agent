"""Minimal RAG over the indexed CV, written as a LangChain chain.

This is the retrieval layer on its own, with no MCP and no tools: retrieve,
stuff into a prompt, answer. It is kept as a reference and as a quick way to
check that indexing and retrieval work before bringing the agent in.

    python rag.py

The chain is LangChain Expression Language (LCEL):

    {context: retrieve, question} | prompt | ChatAnthropic | StrOutputParser
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from config import MAX_TOKENS, MODEL, N_RESULTS, get_collection

collection = get_collection()


def get_context(query: str, n_results: int = N_RESULTS) -> str:
    """Return the indexed chunks most similar to the query."""
    results = collection.query(query_texts=[query], n_results=n_results)
    documents = results.get("documents") or [[]]
    fragments = documents[0]
    if not fragments:
        return "No documents have been indexed yet. Run: python index.py"
    return "\n\n---\n\n".join(fragments)


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Answer the question using only the context provided. "
            "If the answer is not in the context, say so instead of guessing.",
        ),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)

chain = (
    {"context": RunnableLambda(get_context), "question": RunnablePassthrough()}
    | prompt
    | ChatAnthropic(model=MODEL, max_tokens=MAX_TOKENS)
    | StrOutputParser()
)


def ask(query: str) -> str:
    """Answer one question from the indexed documents."""
    return chain.invoke(query)


if __name__ == "__main__":
    question = "What is my experience with machine learning in production?"
    print(ask(question))

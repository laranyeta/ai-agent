"""Index the user's CV and personal documents into the Chroma vector store.

Built with LlamaIndex: it reads every .txt and .md file in DOCS_DIR, splits
each one into overlapping chunks and stores them, with their embeddings, in
the same Chroma collection the agent queries.

    python index.py

The embeddings are computed with Chroma's default function, wrapped for
LlamaIndex. That matters: the agent queries Chroma with `query_texts`, which
embeds the question with that same function, so documents and questions land
in the same vector space.
"""

import logging

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore

from config import CHUNK_OVERLAP, CHUNK_SIZE, DOCS_DIR, get_collection

logger = logging.getLogger(__name__)

EXTENSIONS = [".txt", ".md"]


class ChromaDefaultEmbedding(BaseEmbedding):
    """Expose Chroma's default embedding function as a LlamaIndex embed model.

    LlamaIndex defaults to OpenAI embeddings. Wrapping Chroma's own function
    avoids an extra API key and keeps indexing consistent with retrieval.
    """

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, vector)) for vector in DefaultEmbeddingFunction()(texts)]

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed([query])[0]

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)


def index_dir(directory=DOCS_DIR) -> int:
    """Index every supported document in a directory. Returns the chunk count."""
    if not directory.is_dir():
        raise FileNotFoundError(f"Documents directory not found: {directory}")

    documents = SimpleDirectoryReader(
        input_dir=str(directory), required_exts=EXTENSIONS
    ).load_data()
    if not documents:
        logger.warning("No %s files found in %s", " or ".join(EXTENSIONS), directory)
        return 0

    # The overlap keeps a sentence that straddles a boundary retrievable from
    # either chunk, which matters for a CV where one bullet can carry the
    # whole answer. Sizes are in tokens, not words.
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(documents)

    # Stable ids make re-running idempotent: the same chunk is overwritten
    # instead of duplicated.
    counters: dict[str, int] = {}
    for node in nodes:
        name = node.metadata.get("file_name", "doc")
        node.id_ = f"{name}_{counters.get(name, 0)}"
        counters[name] = counters.get(name, 0) + 1

    storage_context = StorageContext.from_defaults(
        vector_store=ChromaVectorStore(chroma_collection=get_collection())
    )
    VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=ChromaDefaultEmbedding(),
    )
    return len(nodes)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    count = index_dir()
    print(f"[SUCCESS] {count} fragments from {DOCS_DIR} have been indexed.")

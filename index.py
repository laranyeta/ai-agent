"""Index the user's CV and personal documents into the Chroma vector store.

Reads every .txt and .md file in DOCS_DIR, splits each one into overlapping
chunks and upserts them into the collection the agent queries.

    python index.py
"""

import logging

from config import CHUNK_OVERLAP, CHUNK_SIZE, DOCS_DIR, get_collection

logger = logging.getLogger(__name__)

EXTENSIONS = (".txt", ".md")


def split(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks of `size` words that share `overlap` words.

    The overlap keeps a sentence that straddles a boundary retrievable from
    either chunk, which matters for short documents like a CV where one bullet
    point can carry the whole answer.
    """
    if overlap >= size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")

    words = text.split()
    if not words:
        return []

    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + size])
        if chunk:
            chunks.append(chunk)
        if start + size >= len(words):
            break
    return chunks


def index_dir(directory=DOCS_DIR) -> int:
    """Index every supported document in a directory. Returns the chunk count."""
    collection = get_collection()

    if not directory.is_dir():
        raise FileNotFoundError(f"Documents directory not found: {directory}")

    ids, documents, metadatas = [], [], []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8")
        for i, chunk in enumerate(split(text)):
            ids.append(f"{path.name}_{i}")
            documents.append(chunk)
            metadatas.append({"source": path.name, "chunk": i})

    if not documents:
        logger.warning("No %s files found in %s", " or ".join(EXTENSIONS), directory)
        return 0

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(documents)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    count = index_dir()
    print(f"[SUCCESS] {count} fragments from {DOCS_DIR} have been indexed.")

import os
import chromadb

client = chromadb.HttpClient(host="localhost", port=8001)
collection = client.get_or_create_collection(name="my_docs")

def slice(text: str, sz: int = 500) -> list[str]:
    words = text.split()
    slices = []
    for i in range(0, len(words), sz):
        s = " ".join(words[i:i + sz])
        slices.append(s)
    return slices

def index_dir(dir: str):
    ids, docs = [], []
    for filename in os.listdir(dir):
        if not filename.endswith(".txt"):
            continue
        path = os.path.join(dir, filename)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        slices = slice(text)
        for i, s in enumerate(slices):
            ids.append(f"{filename}_{i}")
            docs.append(s)
    collection.upsert(ids=ids, documents=docs)
    print(f"[SUCCESS] {len(docs)} fragments from {dir} have been indexed.")

if __name__ == "__main__":
    index_dir("docs")

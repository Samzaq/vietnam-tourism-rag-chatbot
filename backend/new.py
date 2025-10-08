import json, chromadb
from chromadb.utils import embedding_functions

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("vietnam_docs")

with open("data/corpus_chunks.jsonl", "r", encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f]

collection.add(
    documents=[c["passage"] for c in chunks],
    ids=[str(c["id"]) for c in chunks],
    metadatas=[{"title": c["title"], "len": c["len"]} for c in chunks]
)

query = "Đặc sản nổi tiếng ở Bình Phước là gì?"
results = collection.query(query_texts=[query], n_results=2)

print(results)

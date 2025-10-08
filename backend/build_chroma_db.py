import os
import json
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# Ensure both env vars work on Windows
if not os.getenv("CHROMA_OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY"):
    os.environ["CHROMA_OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

DATA_PATH = "data/corpus_chunks.jsonl"
CHROMA_DB_DIR = "data/chroma_db"

# Initialize Chroma client
client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

# Create OpenAI embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("CHROMA_OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

collection = client.get_or_create_collection(
    name="vietnam_tourism",
    embedding_function=openai_ef
)

# Load data
docs, ids, metas = [], [], []
with open(DATA_PATH, "r", encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        ids.append(str(item["id"]))
        docs.append(item["passage"])
        metas.append({"title": item["title"]})

print(f"Loaded {len(docs)} documents from {DATA_PATH}")

# ---- 🧩 Batch the uploads to stay below the 300k-token limit ----
BATCH_SIZE = 50  # You can tune this (try 50–100)

for i in tqdm(range(0, len(docs), BATCH_SIZE)):
    batch_docs = docs[i:i + BATCH_SIZE]
    batch_ids = ids[i:i + BATCH_SIZE]
    batch_metas = metas[i:i + BATCH_SIZE]

    try:
        collection.add(documents=batch_docs, metadatas=batch_metas, ids=batch_ids)
    except Exception as e:
        print(f"⚠️ Error in batch {i//BATCH_SIZE}: {e}")

print("✅ Finished adding all documents to ChromaDB.")

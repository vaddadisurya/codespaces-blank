import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_core.tools import tool
from app.config import CHROMA_PATH, RAG_DOCS_PATH

_collection = None

def init_chroma():
    global _collection
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    _collection = client.get_or_create_collection(name="bldg59", embedding_function=ef)
    
    # Simple indexing: If empty, read all .txt/.md files in RAG_DOCS_PATH
    if _collection.count() == 0:
        doc_id = 0
        for filename in os.listdir(RAG_DOCS_PATH):
            if filename.endswith((".md", ".txt")):
                with open(os.path.join(RAG_DOCS_PATH, filename), "r", encoding="utf-8") as f:
                    content = f.read()
                    # Storing whole document for simplicity; in production, chunk by headers
                    _collection.add(documents=[content], ids=[f"doc_{doc_id}"])
                    doc_id += 1

@tool
def search_knowledge(query: str) -> str:
    """Search building knowledge base for formulas, thresholds, and system info."""
    if not _collection: return "Database not initialized."
    results = _collection.query(query_texts=[query], n_results=2)
    if not results["documents"] or not results["documents"][0]:
        return "No relevant knowledge found."
    return "\n\n".join(results["documents"][0])
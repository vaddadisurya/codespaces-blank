import os
import json
from azure.storage.blob import BlobServiceClient
from app.config import AZURE_CONN_STR, CONTAINER_FINDINGS, CONTAINER_VISITORS, CONTAINER_RAG, RAG_DOCS_PATH

# Initialize Blob Client
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR) if AZURE_CONN_STR else None

def _ensure_container(container_name):
    if not blob_service_client: return None
    container_client = blob_service_client.get_container_client(container_name)
    if not container_client.exists():
        container_client.create_container()
    return container_client

def sync_rag_documents():
    """Downloads RAG docs from Azure Blob to local disk for ChromaDB indexing."""
    container_client = _ensure_container(CONTAINER_RAG)
    if not container_client: return
    
    for blob in container_client.list_blobs():
        if blob.name.endswith((".md", ".txt")):
            download_path = os.path.join(RAG_DOCS_PATH, blob.name)
            with open(download_path, "wb") as f:
                f.write(container_client.get_blob_client(blob).download_blob().readall())
            print(f"Downloaded RAG document: {blob.name}")

def log_visitor_to_blob(visitor_dict):
    """Appends a visitor line to a single blob file."""
    container_client = _ensure_container(CONTAINER_VISITORS)
    if not container_client: return
    
    blob_client = container_client.get_blob_client("visitors.csv")
    line = f"{visitor_dict['timestamp']},{visitor_dict['name']},{visitor_dict['email']}\n"
    
    if blob_client.exists():
        existing = blob_client.download_blob().readall().decode("utf-8")
        blob_client.upload_blob(existing + line, overwrite=True)
    else:
        blob_client.upload_blob("timestamp,name,email\n" + line)

def save_findings_to_blob(findings_list):
    """Saves the latest 200 findings as a JSON blob."""
    container_client = _ensure_container(CONTAINER_FINDINGS)
    if not container_client: return
    
    blob_client = container_client.get_blob_client("recent_findings.json")
    blob_client.upload_blob(json.dumps(findings_list[-200:], indent=2), overwrite=True)

def load_findings_from_blob():
    """Loads findings from Azure Blob."""
    container_client = _ensure_container(CONTAINER_FINDINGS)
    if not container_client: return []
    
    blob_client = container_client.get_blob_client("recent_findings.json")
    if blob_client.exists():
        return json.loads(blob_client.download_blob().readall())
    return []
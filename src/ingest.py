"""Validated ingestion with bounded embeddings and persistent failure protection."""
import math
import sys
import ollama
from src.chunker import make_chunks
from src.document_loader import load_all_documents
from src.vector_store import COLLECTION_NAME, VECTOR_SIZE, open_store, rebuild_collection, store_chunks
from src.config import workspace_path

EMBEDDING_MODEL = "bge-m3"
DOCS_FOLDER = workspace_path("data/docs")
MODEL_CLIENT = ollama.Client(host="http://127.0.0.1:11434", timeout=120)


def text_to_embed(chunk):
    return chunk["title"] + " - " + chunk["section"] + "\n" + chunk["text"]


def embed_chunks(chunks):
    vectors = []
    for start in range(0, len(chunks), 8):
        batch = chunks[start:start + 8]
        response = MODEL_CLIENT.embed(
            model=EMBEDDING_MODEL, input=[text_to_embed(c) for c in batch], truncate=False)
        if len(response.embeddings) != len(batch):
            raise ValueError("Embedding count differs from document chunk count.")
        for vector in response.embeddings:
            if len(vector) != VECTOR_SIZE or not all(
                type(value) in (int, float) and math.isfinite(value) for value in vector
            ):
                raise ValueError("Embedding has invalid dimensions or numeric values.")
        vectors.extend(response.embeddings)
    return vectors


def main():
    marker = workspace_path("data/index-dirty")
    client = None
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("Rebuild required", encoding="utf-8")
        if not DOCS_FOLDER.is_dir():
            raise ValueError("Document folder does not exist.")
        accepted, rejected = load_all_documents(DOCS_FOLDER)
        print(len(accepted), "documents accepted,", len(rejected), "rejected")
        if rejected:
            print("Rejected files:", ", ".join(name for name, _ in rejected))
            raise ValueError("Fix rejected document headers before rebuilding.")
        chunks = [chunk for document in accepted for chunk in make_chunks(document)]
        if not chunks:
            raise ValueError("No readable content. Use the administrator's rebuild to clear an empty index.")
        vectors = embed_chunks(chunks)
        client = open_store()
        rebuild_collection(client)
        store_chunks(client, chunks, vectors)
        stored = client.count(collection_name=COLLECTION_NAME, exact=True).count
        if stored != len(chunks):
            raise RuntimeError("Stored chunk count differs from the prepared index.")
        client.close()
        client = None
        marker.unlink()
        print(stored, "chunks stored in", COLLECTION_NAME)
        return 0
    except Exception as error:
        # Never remove the marker after a failed or partial rebuild.
        print("Indexing failed (" + type(error).__name__ + "). Questions remain blocked.")
        if isinstance(error, ValueError):
            print(str(error))
        else:
            print("Check Ollama, available disk space, and that no other process has the index open.")
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())

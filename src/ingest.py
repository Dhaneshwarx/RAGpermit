from pathlib import Path

import ollama

from src.chunker import make_chunks
from src.document_loader import load_all_documents
from src.vector_store import COLLECTION_NAME, open_store, rebuild_collection, store_chunks

EMBEDDING_MODEL = "bge-m3"
DOCS_FOLDER = Path("data/docs")


def text_to_embed(chunk):
    # The section title carries meaning the body alone may lack, e.g. "Casual leave".
    return chunk["title"] + " - " + chunk["section"] + "\n" + chunk["text"]


def embed_chunks(chunks):
    texts = [text_to_embed(chunk) for chunk in chunks]
    response = ollama.embed(model=EMBEDDING_MODEL, input=texts)
    vectors = response.embeddings

    # Vector number i must belong to chunk number i. If the counts differ,
    # access fields would end up attached to the wrong text.
    if len(vectors) != len(chunks):
        raise ValueError(
            "got " + str(len(vectors)) + " vectors for " + str(len(chunks)) + " chunks"
        )

    return vectors


def main():
    accepted, rejected = load_all_documents(DOCS_FOLDER)
    print(len(accepted), "documents accepted,", len(rejected), "rejected")
    for file_name, reason in rejected:
        print("REJECTED:", file_name, "->", reason)

    chunks = []
    for document in accepted:
        chunks.extend(make_chunks(document))
    print(len(chunks), "chunks")

    # Embed first. If this step fails, the existing store is left untouched.
    vectors = embed_chunks(chunks)
    print(len(vectors), "vectors of", len(vectors[0]), "numbers each")

    client = open_store()
    rebuild_collection(client)
    store_chunks(client, chunks, vectors)
    stored = client.count(collection_name=COLLECTION_NAME, exact=True).count
    client.close()
    print(stored, "chunks stored in", COLLECTION_NAME)


if __name__ == "__main__":
    main()
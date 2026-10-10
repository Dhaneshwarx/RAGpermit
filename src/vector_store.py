from qdrant_client import QdrantClient, models

COLLECTION_NAME = "permitrag_chunks"
STORAGE_FOLDER = "qdrant_data"
VECTOR_SIZE = 1024  # the size bge-m3 produced in our smoke test


def open_store():
    # Local mode: Qdrant runs inside this Python process and saves to a folder.
    return QdrantClient(path=STORAGE_FOLDER)


def rebuild_collection(client):
    # Always rebuild from scratch. If we only added chunks, a document whose
    # clearance changed (or that was deleted) would leave stale chunks with OLD
    # access fields behind, and stale permissions are an authorization bug.
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )


def store_chunks(client, chunks, vectors):
    if len(chunks) != len(vectors):
        raise ValueError("chunk and vector counts differ")

    points = []
    for number, (chunk, vector) in enumerate(zip(chunks, vectors)):
        # Point IDs must be integers or UUIDs, so we use a counter.
        # The readable chunk_id (like "leave-policy#2") stays in the payload.
        points.append(models.PointStruct(id=number, vector=vector, payload=chunk))

    client.upsert(collection_name=COLLECTION_NAME, points=points)
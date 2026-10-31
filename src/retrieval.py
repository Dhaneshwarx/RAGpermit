import ollama
from qdrant_client import models

from src.authorization import can_read, has_company_access
from src.ingest import EMBEDDING_MODEL
from src.vector_store import COLLECTION_NAME


def build_access_filter(user):
    # Built ONLY from the user's record. The question text never reaches this function.
    if has_company_access(user):
        return models.Filter(must=[
            models.FieldCondition(key="clearance", range=models.Range(lte=user["clearance"]))
        ])
    return models.Filter(
        must=[
            # Clearance check: the chunk's clearance must not be higher than the user's.
            models.FieldCondition(key="clearance", range=models.Range(lte=user["clearance"])),
            # Scope check: department ALL, or the user's department, or the user's role listed.
            models.Filter(
                should=[
                    models.FieldCondition(
                        key="department",
                        match=models.MatchAny(any=["ALL", user["department"]]),
                    ),
                    models.FieldCondition(
                        key="allowed_roles",
                        match=models.MatchValue(value=user["role"]),
                    ),
                ]
            ),
        ]
    )


def search_allowed_chunks(client, user, query_vector, limit):
    # Unknown user: deny without searching at all.
    if user is None:
        return []

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=build_access_filter(user),
        limit=limit,
        with_payload=True,
    )

    results = []
    for hit in response.points:
        payload = hit.payload
        # Second check, with the plain-Python rule from 3.1. If the Qdrant filter and the
        # rule ever disagree, stop with an error instead of returning any text.
        # The message names the chunk only: error messages must never contain chunk text.
        if not can_read(user, payload):
            raise RuntimeError("filter returned a chunk the rule denies: " + str(payload.get("chunk_id")))
        results.append({
            "chunk_id": payload["chunk_id"],
            "doc_id": payload["doc_id"],
            "title": payload["title"],
            "section": payload["section"],
            "text": payload["text"],
            "score": hit.score,
        })
    return results


def retrieve(client, user, question, limit=4):
    from src.config import workspace_path
    if workspace_path('data/index-dirty').exists():
        raise RuntimeError('Document index needs rebuilding')
    if user is None:
        return []
    # The question is used ONLY to compute its embedding. Who is asking comes from `user`.
    question_vector = ollama.embed(model=EMBEDDING_MODEL, input=[question]).embeddings[0]
    return search_allowed_chunks(client, user, question_vector, limit)
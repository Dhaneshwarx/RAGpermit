"""Permission-filtered exact-section retrieval and semantic retrieval."""
import ollama
from qdrant_client import models
from src.authorization import can_read, has_company_access
from src.config import workspace_path
from src.ingest import EMBEDDING_MODEL
from src.section_refs import query_references
from src.vector_store import COLLECTION_NAME

MODEL_CLIENT = ollama.Client(host="http://127.0.0.1:11434", timeout=120)


def build_access_filter(user):
    clearance = models.FieldCondition(key="clearance", range=models.Range(lte=user["clearance"]))
    if has_company_access(user):
        return models.Filter(must=[clearance])
    return models.Filter(must=[
        clearance,
        models.Filter(should=[
            models.FieldCondition(key="department", match=models.MatchAny(any=["ALL", user["department"]])),
            models.FieldCondition(key="allowed_roles", match=models.MatchValue(value=user["role"])),
        ]),
    ])


def checked_chunk(user, payload, score=0.0):
    if not isinstance(payload, dict) or not can_read(user, payload):
        raise RuntimeError("Retrieved payload failed authorization.")
    for field in ("chunk_id", "doc_id", "title", "section", "text"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError("Retrieved payload has invalid content fields.")
    return {**{key: payload[key] for key in ("chunk_id", "doc_id", "title", "section", "text")},
            "score": score, "section_refs": payload.get("section_refs", [])}


def search_allowed_chunks(client, user, query_vector, limit):
    if user is None:
        return []
    result = client.query_points(
        collection_name=COLLECTION_NAME, query=query_vector,
        query_filter=build_access_filter(user), limit=limit, with_payload=True,
    )
    return [checked_chunk(user, hit.payload, hit.score) for hit in result.points]


def search_exact_sections(client, user, references, limit):
    if user is None or not references:
        return []
    restriction = models.Filter(must=[
        build_access_filter(user),
        models.FieldCondition(key="section_refs", match=models.MatchAny(any=references)),
    ])
    points, next_page = client.scroll(
        collection_name=COLLECTION_NAME, scroll_filter=restriction,
        limit=limit + 1, with_payload=True, with_vectors=False,
    )
    # Do not silently omit a jurisdiction/version or a requested section.
    if next_page is not None or len(points) > limit:
        return []
    chunks = [checked_chunk(user, point.payload) for point in points]
    found = {ref for chunk in chunks for ref in chunk["section_refs"]}
    if not set(references).issubset(found):
        return []
    return sorted(chunks, key=lambda chunk: chunk["chunk_id"])


def retrieve(client, user, question, limit=4):
    if user is None:
        return []
    if workspace_path("data/index-dirty").exists():
        raise RuntimeError("Document index needs rebuilding.")
    if not isinstance(question, str) or not question.strip() or not 1 <= limit <= 20:
        raise ValueError("Invalid retrieval request.")
    references = query_references(question)
    if references:
        return search_exact_sections(client, user, references, limit)
    result = MODEL_CLIENT.embed(model=EMBEDDING_MODEL, input=[question], truncate=False)
    if len(result.embeddings) != 1:
        raise ValueError("Embedding response count differs from the request.")
    return search_allowed_chunks(client, user, result.embeddings[0], limit)

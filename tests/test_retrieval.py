import json
from pathlib import Path

from src.authorization import load_users
from src.retrieval import retrieve, search_allowed_chunks
from src.vector_store import COLLECTION_NAME, open_store
from tests.test_access_matrix import MATRIX_FILE, read_matrix

QUESTIONS_FILE = Path("tests/questions.json")
# Any non-zero vector works for the filter test: with a limit above the number of
# chunks, every chunk that passes the filter is returned, so ranking does not matter.
ANY_VECTOR = [1.0] * 1024


def check_filter_against_matrix(client, users):
    matrix = read_matrix(MATRIX_FILE)

    # scroll reads every stored chunk with NO filter. Only this test does that,
    # acting as an inspector. Application code never searches without the filter.
    stored, _ = client.scroll(
        collection_name=COLLECTION_NAME, limit=1000, with_payload=True, with_vectors=False
    )
    total = client.count(collection_name=COLLECTION_NAME, exact=True).count
    assert len(stored) == total, "scroll did not return every chunk"

    pairs = 0
    mismatches = 0
    for user_id, user in users.items():
        returned = search_allowed_chunks(client, user, ANY_VECTOR, limit=1000)
        returned_ids = {chunk["chunk_id"] for chunk in returned}
        assert len(returned_ids) == len(returned), "a chunk was returned twice"
        print(user_id, "may see", len(returned), "of", total, "chunks")

        for point in stored:
            chunk_id = point.payload["chunk_id"]
            expected = matrix[point.payload["doc_id"]][user_id]  # your hand-made answer key
            actual = chunk_id in returned_ids
            pairs += 1
            if actual != expected:
                mismatches += 1
                print("MISMATCH:", user_id, chunk_id, "expected", expected, "got", actual)

    print(pairs, "user-chunk pairs checked,", mismatches, "mismatches")
    assert mismatches == 0

    # An unknown user gets nothing.
    assert search_allowed_chunks(client, None, ANY_VECTOR, limit=1000) == []
    print("Unknown user gets nothing.")


def check_questions(client, users):
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))

    found = 0
    allowed_total = 0
    leaks = 0
    for q in questions:
        user = users.get(q["user_id"])
        assert user is not None, "question " + str(q["id"]) + " names an unknown user"

        results = retrieve(client, user, q["question"], limit=4)
        doc_ids = {chunk["doc_id"] for chunk in results}
        all_text = " ".join(chunk["text"] for chunk in results)

        if q["should_answer"]:
            allowed_total += 1
            if q["source_doc"] in doc_ids:
                found += 1
                verdict = "source found"
            else:
                verdict = "SOURCE NOT IN TOP 4"
        else:
            if q["source_doc"] in doc_ids or q["check_text"] in all_text:
                leaks += 1
                verdict = "LEAK"
            else:
                verdict = "nothing leaked"

        print(q["id"], q["user_id"], "allowed" if q["should_answer"] else "blocked", verdict, sorted(doc_ids))

    print(found, "of", allowed_total, "allowed questions found their source document (quality, not security)")
    print(leaks, "leaks on blocked questions")
    assert leaks == 0


def main():
    users, rejected = load_users()
    assert rejected == [] and len(users) == 6

    client = open_store()
    try:
        check_filter_against_matrix(client, users)
        check_questions(client, users)
    finally:
        client.close()  # always release the Qdrant folder, even if a check failed
    print("Retrieval checks passed.")


if __name__ == "__main__":
    main()
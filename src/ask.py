import sys

from src.answering import answer_question
from src.authorization import load_users
from src.vector_store import open_store


def main():
    if len(sys.argv) != 3:
        print('Usage: python -m src.ask <user_id> "<question>"')
        return

    user_id, question = sys.argv[1], sys.argv[2]

    # AUTHENTICATION STAND-IN: we simply believe the user_id typed here.
    # That is fine for a local test tool and unsafe anywhere else. Real login comes later.
    users, _ = load_users()
    user = users.get(user_id)  # an unknown id gives None, and None gets nothing

    client = open_store()
    try:
                result = answer_question(client, user, question, user_id=user_id)
    finally:
        client.close()

    print(result["answer"])
    if result["sources"]:
        print("Sources:", "; ".join(result["sources"]))
    print("[developer info] status:", result["status"])


if __name__ == "__main__":
    main()
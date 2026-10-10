import ollama

EMBEDDING_MODEL = "bge-m3"
CHAT_MODEL = "qwen3.5:4b"


def check_embedding_model():
    texts = ["Employees get 12 casual leave days per year."]
    response = ollama.embed(model=EMBEDDING_MODEL, input=texts)
    vector = response.embeddings[0]
    print("Number in the vector:", len(vector))
    print("first 5 numbers:", vector[:5])


def check_chat_model():
    context = "Employees get 12 casual leave days per year."
    question = "How many casual leave days do employees get per year?"
    prompt = f"Answer using only this text.\n\nText: {context}\n\nQuestion: {question}"
    response = ollama.chat(
        model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            think=False,
            )
    print("Answer:", response.message.content)
    print("Raw message:", response.message)

check_embedding_model()
check_chat_model()
# test_rag.py

from rag.rag_chain import answer_query

while True:

    query = input("\nUser: ")

    if query.lower() == "exit":
        break

    response = answer_query(query)

    print("\nBot:")
    print(response)

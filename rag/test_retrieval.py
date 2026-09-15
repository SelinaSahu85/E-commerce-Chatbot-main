from rag.retriever import get_documents

while True:

    query = input("\nQuestion: ")

    if query.lower() == "exit":
        break

    docs = get_documents(query)

    print("\n" + "=" * 100)
    print("RETRIEVED DOCUMENTS")
    print("=" * 100)

    for i, doc in enumerate(docs, 1):

        print(f"\nDocument {i}")
        print("-" * 80)

        print(doc.page_content)

        print("\nMetadata:")
        print(doc.metadata)

        print("-" * 80)
import os

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from rag.embeddings import get_embedding_model
from config.setting import KNOWLEDGE_BASE_DIR, VECTORSTORE_PATH

_LOADERS_BY_EXTENSION = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
    ".docx": Docx2txtLoader,
}


def load_knowledge_base_documents():

    documents = []

    for filename in sorted(os.listdir(KNOWLEDGE_BASE_DIR)):

        file_path = os.path.join(KNOWLEDGE_BASE_DIR, filename)

        _, ext = os.path.splitext(filename)

        loader_cls = _LOADERS_BY_EXTENSION.get(ext.lower())

        if loader_cls is None:
            print(f"Skipping unsupported file: {filename}")
            continue

        print(f"Loading {filename}...")

        loader = loader_cls(file_path)

        docs = loader.load()

        for doc in docs:
            doc.metadata["source"] = filename

        documents.extend(docs)

    return documents


def build_vectorstore():

    print("Loading knowledge base documents...")

    documents = load_knowledge_base_documents()

    print(f"Documents Loaded : {len(documents)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=[
            "\n\n",
            "\n",
            "?",
            ".",
            " "
        ]
    )

    chunks = splitter.split_documents(documents)

    print(f"Chunks Created : {len(chunks)}")

    valid_chunks = [
        chunk for chunk in chunks if chunk.page_content.strip()
    ]

    print(f"Valid Chunks : {len(valid_chunks)}")

    if not valid_chunks:
        raise ValueError("No chunks found after splitting")

    embeddings = get_embedding_model()

    test_embedding = embeddings.embed_query(
        "What is the return policy?"
    )

    print(
        f"Embedding Dimension : {len(test_embedding)}"
    )

    vectorstore = FAISS.from_documents(
        valid_chunks,
        embeddings
    )

    os.makedirs(os.path.dirname(VECTORSTORE_PATH), exist_ok=True)

    vectorstore.save_local(
        str(VECTORSTORE_PATH)
    )

    print("Vector Store Saved Successfully")


if __name__ == "__main__":
    build_vectorstore()

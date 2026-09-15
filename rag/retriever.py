from langchain_community.vectorstores import FAISS

from rag.embeddings import get_embedding_model
from config.setting import VECTORSTORE_PATH

_vectorstore = None


def get_vectorstore():

    global _vectorstore

    if _vectorstore is None:

        embeddings = get_embedding_model()

        _vectorstore = FAISS.load_local(
            str(VECTORSTORE_PATH),
            embeddings,
            allow_dangerous_deserialization=True
        )

    return _vectorstore


def get_retriever():
    """
    Returns a Retriever object for RAG.
    """

    db = get_vectorstore()

    retriever = db.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 6,
            "fetch_k": 20,
            "lambda_mult": 0.7
        }
    )

    return retriever


def get_documents(query: str):
    """
    Helper function for debugging retrieval.
    """

    retriever = get_retriever()

    docs = retriever.invoke(query)

    return docs


def get_documents_with_scores(query: str, k: int = 6):
    """
    Returns [(doc, score), ...]. With normalized embeddings, FAISS's
    default L2 distance is in [0, 2]; we convert it to a 0-1 similarity
    score (1 = most similar) for the enquiry agent's confidence check.
    """

    db = get_vectorstore()

    results = db.similarity_search_with_score(query, k=k)

    scored = []

    for doc, distance in results:
        similarity = max(0.0, 1.0 - (distance / 2.0))
        scored.append((doc, similarity))

    return scored
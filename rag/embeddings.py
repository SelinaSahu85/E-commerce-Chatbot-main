from langchain_huggingface import HuggingFaceEmbeddings

# Local model path
_EMBEDDING_MODEL_PATH = (
    r"C:\Users\Selina.Sahu\Downloads\all-MiniLM-L6-v2"
)

_embedding_model = None


def get_embedding_model():
    """
    Returns a cached HuggingFace embedding model instance.
    Loads from local disk instead of downloading from Hugging Face.
    """

    global _embedding_model

    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name=_EMBEDDING_MODEL_PATH,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    return _embedding_model

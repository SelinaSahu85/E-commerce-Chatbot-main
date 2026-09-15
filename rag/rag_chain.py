from langchain_google_genai import ChatGoogleGenerativeAI
from rag.retriever import get_documents_with_scores

from prompts.enquiry_prompt import RAG_ANSWER_PROMPT
from config.setting import RAG_SCORE_THRESHOLD, GEMINI_MODEL
from utils.helpers import extract_llm_text

from dotenv import load_dotenv
import os

load_dotenv()


def answer_query(query):

    scored_docs = get_documents_with_scores(query)

    docs = [doc for doc, _ in scored_docs]

    confidence = max((score for _, score in scored_docs), default=0.0)

    context = "\n\n".join(
        [doc.page_content for doc in docs]
    )

    sources = []

    for doc in docs:

        source_name = doc.metadata.get("source", "Knowledge Base")
        page_num = doc.metadata.get("page")

        if page_num is not None:
            sources.append(f"{source_name} (page {page_num})")
        else:
            sources.append(source_name)

    if confidence < RAG_SCORE_THRESHOLD or not context.strip():

        return {
            "answer": None,
            "sources": [],
            "confidence": confidence,
            "sufficient": False,
        }

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

    prompt = RAG_ANSWER_PROMPT.format(context=context, query=query)

    response = llm.invoke(prompt)

    return {
        "answer": extract_llm_text(response),
        "sources": list(dict.fromkeys(sources)),
        "confidence": confidence,
        "sufficient": True,
    }

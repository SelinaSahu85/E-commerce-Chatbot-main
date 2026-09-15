from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

from tools.guardrails import check_guardrails
from utils.helpers import extract_llm_text
from prompts.enquiry_prompt import SAFETY_CHECK_PROMPT
from config.setting import GEMINI_MODEL

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)


def can_answer_safely(query: str) -> bool:
    """
    Deterministic guardrails run first (cheap, no LLM call needed to
    reject obviously restricted/sensitive requests); only genuinely
    ambiguous queries fall through to the LLM safety classifier.
    """

    guard_result = check_guardrails(query)

    if guard_result["blocked"]:
        return False

    response = llm.invoke(SAFETY_CHECK_PROMPT.format(query=query))

    result = extract_llm_text(response).strip().upper()

    return result == "SAFE"

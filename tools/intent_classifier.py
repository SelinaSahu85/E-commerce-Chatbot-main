from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from utils.logger import logger
from utils.helpers import extract_llm_text
from prompts.supervisor_prompt import INTENT_CLASSIFICATION_PROMPT
from config.setting import GEMINI_MODEL
import os

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)


def classify_intent(query: str) -> str:
    """
    Classify query as enquiry or complaint
    """

    prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query)

    try:

        logger.info(f"Classifying Query: {query}")

        response = llm.invoke(prompt)

        content = extract_llm_text(response)

        logger.info(f"Raw Response: {content}")

        intent = content.strip().lower()

        logger.info(f"Extracted Intent: {intent}")

        if "complaint" in intent:
            return "complaint"

        return "enquiry"

    except Exception as e:

        logger.error(f"Intent Classification Failed: {str(e)}")

        logger.info("Using Rule-Based Fallback")

        query_lower = query.lower()

        complaint_keywords = [
            "damaged",
            "broken",
            "cracked",
            "refund",
            "missing",
            "wrong item",
            "wrong product",
            "late delivery",
            "not delivered",
            "complaint",
            "issue",
            "problem",
            "defective",
            "received damaged",
            "cancelled order",
            "screen cracked"
        ]

        if any(keyword in query_lower for keyword in complaint_keywords):
            logger.info("Fallback Intent: complaint")
            return "complaint"

        logger.info("Fallback Intent: enquiry")
        return "enquiry"
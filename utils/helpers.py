def extract_llm_text(response) -> str:
    """
    Normalizes a LangChain chat model response's `.content` into plain
    text. Depending on the model/SDK version, `.content` may be a plain
    string, or a list of content blocks (e.g.
    [{"type": "text", "text": "...", "extras": {...}}]) — newer Gemini
    models return the latter.
    """

    content = response.content if hasattr(response, "content") else response

    if isinstance(content, str):
        return content

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
            else:
                parts.append(str(item))

        return " ".join(parts)

    return str(content)

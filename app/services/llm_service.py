"""
LLM Service — provider-agnostic chat completion via OpenAI-compatible API.

Currently backed by Gemini (Google Generative Language, OpenAI-compatible endpoint).
The application talks to this service, not directly to a provider, so the
provider/model can change via config without touching business logic.
"""

from typing import List, Dict
import httpx
from app.config import settings
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.llm_service")


class LLMServiceError(Exception):
    """Raised when the LLM provider call fails."""
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


async def ask(
    system_prompt: str,
    context: str,
    question: str,
    history: List[Dict[str, str]] = None,
    temperature: float = 0.2,
) -> str:
    """
    Send a grounded chat completion request to the LLM.

    Message order:
        system → history (user/assistant) → user (context + question)

    The system prompt is owned by the backend. The frontend cannot supply it.

    Raises:
        LLMServiceError on missing config or provider failure.
    """
    if not settings.LLM_API_KEY:
        raise LLMServiceError("LLM is not configured (missing API key)", status_code=503)

    messages = [{"role": "system", "content": system_prompt}]

    # Include prior conversation turns (already validated + capped by caller)
    if history:
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Final user message carries the drug context + the actual question
    user_content = f"{context}\n\n---\n\nDOCTOR'S QUESTION:\n{question}"
    messages.append({"role": "user", "content": user_content})

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.ConnectError:
        logger.error("LLM connection error")
        raise LLMServiceError("Cannot connect to the AI service", status_code=503)
    except httpx.TimeoutException:
        logger.error("LLM request timed out")
        raise LLMServiceError("AI service timed out", status_code=504)

    if response.status_code != 200:
        # Do not log the API key; log status + a short snippet of the body
        logger.error(f"LLM error: HTTP {response.status_code} | {response.text[:300]}")
        raise LLMServiceError("AI service returned an error", status_code=502)

    try:
        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Unexpected LLM response shape: {e} | {response.text[:300]}")
        raise LLMServiceError("AI service returned an unexpected response", status_code=502)

    if not answer:
        raise LLMServiceError("AI service returned an empty answer", status_code=502)

    return answer

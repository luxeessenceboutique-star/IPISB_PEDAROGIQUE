import json
import logging
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI

from deps import get_current_user, CurrentUser
from copilot.agent import copilot_graph, LANG_SYSTEM, BASE_URL, API_KEY, CHAT_MODEL

router = APIRouter(prefix="/copilot", tags=["copilot"])
log = logging.getLogger(__name__)


class CopilotRequest(BaseModel):
    messages: list[dict]
    language: str = "fr"


def _role_of(user: CurrentUser) -> str:
    if user.is_admin():
        return "admin"
    if user.is_prof():
        return "professor"
    return "student"


def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)


@router.post("/stream")
async def copilot_stream(
    req: CopilotRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """SSE streaming endpoint for the in-app platform copilot, available to every
    authenticated role. Yields `data: {"text": "..."}` chunks then `data: [DONE]`."""
    role = _role_of(user)

    try:
        state = await copilot_graph.ainvoke({
            "messages": req.messages,
            "role": role,
            "language": req.language,
            "intent": "",
            "system_prompt": "",
        })
        system_prompt = state.get("system_prompt", "")
    except Exception as exc:
        log.warning("Copilot graph failed: %s", exc)
        system_prompt = "Tu es le Copilote IPISB Connect, assistant d'aide à l'utilisation de la plateforme."

    lang_instr = LANG_SYSTEM.get(req.language, LANG_SYSTEM["fr"])
    full_system = f"{lang_instr}\n\n{system_prompt}"

    async def generate():
        client = _openai_client()
        try:
            stream = await client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[{"role": "system", "content": full_system}] + req.messages,
                max_tokens=700,
                temperature=0.4,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield f"data: {json.dumps({'text': delta.content})}\n\n"
        except Exception as e:
            log.error("Copilot LLM stream error: %s", e)
            yield f"data: {json.dumps({'text': f'Erreur: {type(e).__name__}: {e}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def copilot_health():
    return {"ok": True, "model": CHAT_MODEL}

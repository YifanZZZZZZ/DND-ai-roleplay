import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.app.api.dependencies import DatabaseSession
from backend.app.events import get_session_event_hub
from backend.app.events.hub import SessionEvent, SessionEventHub
from backend.app.services.campaign_service import CampaignService

router = APIRouter(tags=["events"])


def serialize_event(event: SessionEvent) -> str:
    payload = json.dumps({"sessionId": event.session_id}, separators=(",", ":"))
    return f"event: {event.event_type}\ndata: {payload}\n\n"


async def event_stream(
    request: Request, session_id: str, hub: SessionEventHub
) -> AsyncGenerator[str, None]:
    queue = await hub.subscribe(session_id)
    try:
        yield "event: ready\ndata: {}\n\n"
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield serialize_event(event)
    finally:
        await hub.unsubscribe(session_id, queue)


@router.get("/sessions/{session_id}/events")
async def get_session_events(
    session_id: str, request: Request, session: DatabaseSession
) -> StreamingResponse:
    await CampaignService(session).get_session(session_id)
    return StreamingResponse(
        event_stream(request, session_id, get_session_event_hub()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

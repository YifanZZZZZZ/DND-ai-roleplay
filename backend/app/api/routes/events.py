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


def serialize_event(event: SessionEvent, campaign_id: str) -> str:
    payload = json.dumps({"campaignId": campaign_id}, separators=(",", ":"))
    return f"event: {event.event_type}\ndata: {payload}\n\n"


async def event_stream(
    request: Request, session_id: str, campaign_id: str, hub: SessionEventHub
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
            yield serialize_event(event, campaign_id)
    finally:
        await hub.unsubscribe(session_id, queue)


@router.get("/campaigns/{campaign_id}/events")
async def get_campaign_events(
    campaign_id: str, request: Request, session: DatabaseSession
) -> StreamingResponse:
    game_session = await CampaignService(session).get_campaign_runtime(campaign_id)
    return StreamingResponse(
        event_stream(request, game_session.id, campaign_id, get_session_event_hub()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

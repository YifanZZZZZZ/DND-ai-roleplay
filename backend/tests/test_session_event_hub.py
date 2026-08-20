import asyncio

from backend.app.events.hub import SessionEventHub


async def test_session_event_hub_delivers_events_only_to_the_matching_session() -> None:
    hub = SessionEventHub()
    matching_queue = await hub.subscribe("session-a")
    other_queue = await hub.subscribe("session-b")

    await hub.publish("message.created", "session-a")

    event = await asyncio.wait_for(matching_queue.get(), timeout=0.1)
    assert event.event_type == "message.created"
    assert event.session_id == "session-a"
    assert other_queue.empty()

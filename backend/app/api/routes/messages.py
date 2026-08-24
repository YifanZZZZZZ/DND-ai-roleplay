from fastapi import APIRouter, status

from backend.app.api.dependencies import DatabaseSession
from backend.app.api.schemas.messages import (
    DmMessageCommandResult,
    DmMessageCreate,
    MessageRecipientView,
    MessageView,
    OocCorrectionCreate,
    RuntimeState,
)
from backend.app.db.models import GameSession, Message
from backend.app.events import get_session_event_hub
from backend.app.runtime import get_runtime_supervisor
from backend.app.services.message_service import MessageService

router = APIRouter(tags=["messages"])


def to_runtime_state(game_session: GameSession) -> RuntimeState:
    runtime = game_session.runtime
    return RuntimeState(
        status=runtime.status,
        generation=runtime.generation,
        active_agent_run_id=runtime.active_agent_run_id,
        waiting_request=runtime.waiting_request,
        last_error_code=runtime.last_error_code,
        last_error_message=runtime.last_error_message,
        consecutive_ai_messages=runtime.consecutive_ai_messages,
    )


def to_message_view(message: Message) -> MessageView:
    return MessageView(
        id=message.id,
        campaign_id=message.session.campaign_id,
        sequence_no=message.sequence_no,
        sender_type=message.sender_type,
        sender_character_id=message.sender_character_id,
        sender_name=message.sender_character.name if message.sender_character else None,
        kind=message.kind,
        audience=message.audience,
        content=message.content,
        addressed_character_ids=list(message.addressed_character_ids or []),
        is_ooc_corrected=message.ooc_correction_note is not None,
        ooc_correction_note=message.ooc_correction_note,
        recipients=[
            MessageRecipientView(character_id=recipient.character_id, name=recipient.character.name)
            for recipient in message.recipients
        ],
        created_at=message.created_at,
    )


@router.get("/campaigns/{campaign_id}/messages", response_model=list[MessageView])
async def list_messages(campaign_id: str, session: DatabaseSession) -> list[MessageView]:
    messages = await MessageService(session).list_for_campaign(campaign_id)
    return [to_message_view(message) for message in messages]


@router.post(
    "/campaigns/{campaign_id}/messages",
    response_model=DmMessageCommandResult,
    status_code=status.HTTP_201_CREATED,
)
async def send_dm_message(
    campaign_id: str, payload: DmMessageCreate, session: DatabaseSession
) -> DmMessageCommandResult:
    message, game_session = await MessageService(session).send_dm_message_for_campaign(
        campaign_id, payload
    )
    event_hub = get_session_event_hub()
    await event_hub.publish("message.created", game_session.id)
    await event_hub.publish("runtime.changed", game_session.id)
    if game_session.runtime.active_agent_run_id is not None:
        get_runtime_supervisor().start(game_session.runtime.active_agent_run_id)
    return DmMessageCommandResult(
        message=to_message_view(message), runtime=to_runtime_state(game_session)
    )


@router.post("/campaigns/{campaign_id}/messages:ooc", response_model=RuntimeState)
async def correct_message_with_ooc(
    campaign_id: str, payload: OocCorrectionCreate, session: DatabaseSession
) -> RuntimeState:
    game_session = await MessageService(session).correct_with_ooc_for_campaign(campaign_id, payload)
    await get_session_event_hub().publish("message.created", game_session.id)
    await get_session_event_hub().publish("runtime.changed", game_session.id)
    if game_session.runtime.active_agent_run_id is not None:
        get_runtime_supervisor().start(game_session.runtime.active_agent_run_id)
    return to_runtime_state(game_session)


@router.post("/campaigns/{campaign_id}/runtime:stop", response_model=RuntimeState)
async def stop_runtime(campaign_id: str, session: DatabaseSession) -> RuntimeState:
    game_session = await MessageService(session).stop_runtime_for_campaign(campaign_id)
    await get_session_event_hub().publish("runtime.changed", game_session.id)
    return to_runtime_state(game_session)


@router.post("/campaigns/{campaign_id}/runtime:retry", response_model=RuntimeState)
async def retry_runtime(campaign_id: str, session: DatabaseSession) -> RuntimeState:
    game_session = await MessageService(session).retry_latest_for_campaign(campaign_id)
    await get_session_event_hub().publish("runtime.changed", game_session.id)
    if game_session.runtime.active_agent_run_id is not None:
        get_runtime_supervisor().start(game_session.runtime.active_agent_run_id)
    return to_runtime_state(game_session)

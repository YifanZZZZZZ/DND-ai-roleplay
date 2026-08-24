# ruff: noqa: E501
from uuid import uuid4

from fastapi import APIRouter, status

from backend.app.api.dependencies import DatabaseSession
from backend.app.api.schemas.dm_drafts import (
    DmDraftCreate,
    DmDraftPublishResult,
    DmDraftUpdate,
    DmDraftView,
)
from backend.app.api.schemas.messages import DmMessageCreate
from backend.app.core.errors import ConflictError
from backend.app.db.models import CampaignDmDraft
from backend.app.domain.enums import DmDraftStatus
from backend.app.events import get_session_event_hub
from backend.app.runtime import get_runtime_supervisor
from backend.app.services.dm_draft_service import DmDraftService
from backend.app.services.message_service import MessageService

router = APIRouter(tags=["dm-drafts"])


def view(draft: CampaignDmDraft) -> DmDraftView:
    return DmDraftView.model_validate(draft, from_attributes=True)


@router.post(
    "/campaigns/{campaign_id}/dm-drafts",
    response_model=DmDraftView,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    campaign_id: str, payload: DmDraftCreate, session: DatabaseSession
) -> DmDraftView:
    return view(
        await DmDraftService(session).create(
            campaign_id, payload.prompt, payload.source_skill_check_id, payload.assist_mode
        )
    )


@router.get("/campaigns/{campaign_id}/dm-drafts", response_model=list[DmDraftView])
async def list_drafts(campaign_id: str, session: DatabaseSession) -> list[DmDraftView]:
    return [view(item) for item in await DmDraftService(session).list(campaign_id)]


@router.post("/campaigns/{campaign_id}/dm-drafts:generate-opening", response_model=DmDraftView)
async def generate_opening(campaign_id: str, session: DatabaseSession) -> DmDraftView:
    return view(await DmDraftService(session).generate_opening(campaign_id))


@router.patch("/dm-drafts/{draft_id}", response_model=DmDraftView)
async def update_draft(
    draft_id: str, payload: DmDraftUpdate, session: DatabaseSession
) -> DmDraftView:
    return view(await DmDraftService(session).update(draft_id, payload))


@router.post("/dm-drafts/{draft_id}:discard", response_model=DmDraftView)
async def discard_draft(draft_id: str, session: DatabaseSession) -> DmDraftView:
    return view(await DmDraftService(session).discard(draft_id))


@router.post("/dm-drafts/{draft_id}:publish", response_model=DmDraftPublishResult)
async def publish_draft(draft_id: str, session: DatabaseSession) -> DmDraftPublishResult:
    service = DmDraftService(session)
    draft = await service.get(draft_id)
    if draft.status not in (DmDraftStatus.READY, DmDraftStatus.DRAFT) or not draft.content.strip():
        raise ConflictError("DM_DRAFT_NOT_READY", "只有已准备好的非空草稿才能发布。")
    if draft.trigger_type.value == "OPENING":
        from backend.app.services.campaign_service import CampaignService

        await CampaignService(session).activate(draft.campaign_id)
    result = await MessageService(session).send_dm_message_for_campaign(
        draft.campaign_id,
        DmMessageCreate(
            content=draft.content,
            audience=draft.audience,
            recipient_character_ids=draft.recipient_character_ids,
            client_request_id=uuid4(),
        ),
    )
    await service.mark_published(draft_id, result[1].id)
    await get_session_event_hub().publish("message.created", result[1].id)
    await get_session_event_hub().publish("runtime.changed", result[1].id)
    if result[1].runtime.active_agent_run_id is not None:
        get_runtime_supervisor().start(result[1].runtime.active_agent_run_id)
    from backend.app.api.routes.messages import to_message_view

    return DmDraftPublishResult(
        draft=view(await service.get(draft_id)), message=to_message_view(result[0])
    )

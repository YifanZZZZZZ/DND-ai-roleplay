from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from backend.app.api.dependencies import DatabaseSession
from backend.app.api.schemas.campaigns import (
    CampaignCreate,
    CampaignDetail,
    CampaignMember,
    CampaignMemberAdd,
    CampaignMembershipUpdate,
    CampaignSummary,
    CampaignUpdate,
    HpState,
    HpUpdate,
    SessionCreate,
    SessionDetail,
    SessionSummary,
)
from backend.app.db.models import Campaign, GameSession
from backend.app.domain.enums import SessionStatus
from backend.app.events import get_session_event_hub
from backend.app.services.campaign_service import CampaignService
from backend.app.services.export_service import ExportService

router = APIRouter(tags=["campaigns"])


def to_campaign_summary(campaign: Campaign) -> CampaignSummary:
    active_session = next(
        (item for item in campaign.sessions if item.status == SessionStatus.ACTIVE), None
    )
    return CampaignSummary(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        lifecycle_status=campaign.lifecycle_status,
        archived_at=campaign.archived_at,
        revision=campaign.revision,
        member_count=len(campaign.memberships),
        active_session_id=active_session.id if active_session else None,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


def to_campaign_detail(campaign: Campaign) -> CampaignDetail:
    summary = to_campaign_summary(campaign)
    return CampaignDetail(
        **summary.model_dump(),
        members=[
            CampaignMember(
                character_id=membership.character.id,
                name=membership.character.name,
                max_hp=membership.character.max_hp,
                avatar_path=membership.character.avatar_path,
                is_configured=bool(membership.character.roleplay_prompt.strip())
                and membership.character.active_sheet_version_id is not None,
            )
            for membership in campaign.memberships
        ],
        sessions=[
            SessionSummary(
                id=game_session.id,
                title=game_session.title,
                status=game_session.status,
                started_at=game_session.started_at,
                ended_at=game_session.ended_at,
            )
            for game_session in sorted(campaign.sessions, key=lambda item: item.started_at)
        ],
    )


def to_session_detail(game_session: GameSession) -> SessionDetail:
    return SessionDetail(
        id=game_session.id,
        campaign_id=game_session.campaign_id,
        title=game_session.title,
        status=game_session.status,
        runtime_status=game_session.runtime.status,
        runtime_generation=game_session.runtime.generation,
        active_agent_run_id=game_session.runtime.active_agent_run_id,
        waiting_request=game_session.runtime.waiting_request,
        last_error_code=game_session.runtime.last_error_code,
        last_error_message=game_session.runtime.last_error_message,
        consecutive_ai_messages=game_session.runtime.consecutive_ai_messages,
        hp_states=[
            HpState(
                character_id=state.character_id,
                name=state.character.name,
                current_hp=state.current_hp,
                max_hp=state.max_hp_snapshot,
            )
            for state in game_session.character_states
        ],
        started_at=game_session.started_at,
        ended_at=game_session.ended_at,
    )


@router.get("/campaigns", response_model=list[CampaignSummary])
async def list_campaigns(session: DatabaseSession) -> list[CampaignSummary]:
    campaigns = await CampaignService(session).list()
    return [to_campaign_summary(campaign) for campaign in campaigns]


@router.post("/campaigns", response_model=CampaignDetail, status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignCreate, session: DatabaseSession) -> CampaignDetail:
    campaign = await CampaignService(session).create(payload)
    return to_campaign_detail(campaign)


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    campaign = await CampaignService(session).get(campaign_id)
    return to_campaign_detail(campaign)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def update_campaign(
    campaign_id: str, payload: CampaignUpdate, session: DatabaseSession
) -> CampaignDetail:
    campaign = await CampaignService(session).update(campaign_id, payload)
    return to_campaign_detail(campaign)


@router.put("/campaigns/{campaign_id}/memberships", response_model=CampaignDetail)
async def replace_memberships(
    campaign_id: str, payload: CampaignMembershipUpdate, session: DatabaseSession
) -> CampaignDetail:
    campaign = await CampaignService(session).replace_memberships(campaign_id, payload)
    return to_campaign_detail(campaign)


@router.post("/campaigns/{campaign_id}/members", response_model=CampaignDetail)
async def add_campaign_member(
    campaign_id: str, payload: CampaignMemberAdd, session: DatabaseSession
) -> CampaignDetail:
    campaign = await CampaignService(session).add_member(campaign_id, payload)
    return to_campaign_detail(campaign)


@router.post("/campaigns/{campaign_id}:activate", response_model=CampaignDetail)
async def activate_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    campaign = await CampaignService(session).activate(campaign_id)
    return to_campaign_detail(campaign)


@router.post("/campaigns/{campaign_id}:complete", response_model=CampaignDetail)
async def complete_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    campaign = await CampaignService(session).complete(campaign_id)
    return to_campaign_detail(campaign)


@router.post("/campaigns/{campaign_id}:reopen", response_model=CampaignDetail)
async def reopen_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    campaign = await CampaignService(session).reopen(campaign_id)
    return to_campaign_detail(campaign)


@router.post("/campaigns/{campaign_id}:archive", response_model=CampaignDetail)
async def archive_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    return to_campaign_detail(await CampaignService(session).archive(campaign_id))


@router.post("/campaigns/{campaign_id}:unarchive", response_model=CampaignDetail)
async def unarchive_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    return to_campaign_detail(await CampaignService(session).unarchive(campaign_id))


@router.post("/campaigns/{campaign_id}:reset", response_model=CampaignDetail)
async def reset_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    return to_campaign_detail(await CampaignService(session).reset(campaign_id))


@router.get("/campaigns/{campaign_id}:export")
async def export_campaign(campaign_id: str, session: DatabaseSession) -> JSONResponse:
    return JSONResponse(await ExportService(session).campaign(campaign_id))


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: str, session: DatabaseSession) -> None:
    await CampaignService(session).delete(campaign_id)


@router.post(
    "/campaigns/{campaign_id}/sessions",
    response_model=SessionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    campaign_id: str, payload: SessionCreate, session: DatabaseSession
) -> SessionDetail:
    game_session = await CampaignService(session).create_session(campaign_id, payload)
    return to_session_detail(game_session)


@router.post("/sessions/{session_id}:end", response_model=SessionDetail)
async def end_session(session_id: str, session: DatabaseSession) -> SessionDetail:
    game_session = await CampaignService(session).end_session(session_id)
    await get_session_event_hub().publish("runtime.changed", session_id)
    return to_session_detail(game_session)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, session: DatabaseSession) -> SessionDetail:
    game_session = await CampaignService(session).get_session(session_id)
    return to_session_detail(game_session)


@router.patch("/sessions/{session_id}/characters/{character_id}/hp", response_model=SessionDetail)
async def update_hp(
    session_id: str,
    character_id: str,
    payload: HpUpdate,
    session: DatabaseSession,
) -> SessionDetail:
    game_session = await CampaignService(session).update_hp(session_id, character_id, payload)
    await get_session_event_hub().publish("hp.changed", session_id)
    return to_session_detail(game_session)

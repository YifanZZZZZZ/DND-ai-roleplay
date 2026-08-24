from fastapi import APIRouter, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select

from backend.app.api.dependencies import DatabaseSession
from backend.app.api.schemas.campaigns import (
    CampaignCreate,
    CampaignDetail,
    CampaignMember,
    CampaignMemberAdd,
    CampaignMembershipUpdate,
    CampaignPlayState,
    CampaignSummary,
    CampaignUpdate,
    CharacterAcquaintanceView,
    HpState,
    HpUpdate,
)
from backend.app.api.schemas.characters import CampaignSkillMemberView
from backend.app.api.schemas.skill_checks import (
    SkillCheckAdjudicate,
    SkillCheckCreate,
    SkillCheckView,
    SkillCheckVoid,
)
from backend.app.api.schemas.summaries import CampaignSummaryView
from backend.app.db.models import Campaign, GameSession, SessionSummary
from backend.app.events import get_session_event_hub
from backend.app.services.acquaintance_service import AcquaintanceService
from backend.app.services.campaign_service import CampaignService
from backend.app.services.export_service import ExportService
from backend.app.services.skill_check_service import SkillCheckService

router = APIRouter(tags=["campaigns"])


def to_campaign_summary(campaign: Campaign) -> CampaignSummary:
    return CampaignSummary(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        dm_guide=campaign.dm_guide,
        scene_notes=campaign.scene_notes,
        module_content=campaign.module_content,
        style_instructions=campaign.style_instructions,
        opening_instructions=campaign.opening_instructions,
        play_mode=campaign.play_mode,
        lifecycle_status=campaign.lifecycle_status,
        archived_at=campaign.archived_at,
        revision=campaign.revision,
        member_count=len(campaign.memberships),
        has_runtime=bool(campaign.sessions),
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
    )


def to_play_state(game_session: GameSession) -> CampaignPlayState:
    return CampaignPlayState(
        campaign_id=game_session.campaign_id,
        lifecycle_status=game_session.campaign.lifecycle_status,
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


@router.get("/campaigns/{campaign_id}:export")
async def export_campaign(campaign_id: str, session: DatabaseSession) -> JSONResponse:
    return JSONResponse(jsonable_encoder(await ExportService(session).campaign(campaign_id)))


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


@router.get(
    "/campaigns/{campaign_id}/acquaintances",
    response_model=list[CharacterAcquaintanceView],
)
async def list_campaign_acquaintances(
    campaign_id: str, session: DatabaseSession
) -> list[CharacterAcquaintanceView]:
    pairs = await AcquaintanceService(session).list_for_campaign(campaign_id)
    return [
        CharacterAcquaintanceView(
            character_a_id=character_a.id,
            character_a_name=character_a.name,
            character_b_id=character_b.id,
            character_b_name=character_b.name,
            acquainted=acquaintance is not None,
            relationship_history=(
                acquaintance.relationship_history if acquaintance is not None else ""
            ),
        )
        for character_a, character_b, acquaintance in pairs
    ]


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


@router.post("/campaigns/{campaign_id}:pause", response_model=CampaignDetail)
async def pause_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    campaign = await CampaignService(session).pause(campaign_id)
    if campaign.sessions:
        await get_session_event_hub().publish("campaign.changed", campaign.sessions[0].id)
    return to_campaign_detail(campaign)


@router.post("/campaigns/{campaign_id}:resume", response_model=CampaignDetail)
async def resume_campaign(campaign_id: str, session: DatabaseSession) -> CampaignDetail:
    campaign = await CampaignService(session).resume(campaign_id)
    if campaign.sessions:
        await get_session_event_hub().publish("campaign.changed", campaign.sessions[0].id)
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


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: str, session: DatabaseSession) -> None:
    await CampaignService(session).delete(campaign_id)


@router.get("/campaigns/{campaign_id}/play", response_model=CampaignPlayState)
async def get_campaign_play_state(campaign_id: str, session: DatabaseSession) -> CampaignPlayState:
    game_session = await CampaignService(session).get_campaign_runtime(campaign_id)
    return to_play_state(game_session)


@router.get("/campaigns/{campaign_id}/summaries", response_model=list[CampaignSummaryView])
async def list_campaign_summaries(
    campaign_id: str, session: DatabaseSession
) -> list[CampaignSummaryView]:
    await CampaignService(session).get(campaign_id)
    summaries = await session.scalars(
        select(SessionSummary).where(SessionSummary.session.has(campaign_id=campaign_id))
    )
    return [
        CampaignSummaryView(
            id=item.id,
            campaign_id=campaign_id,
            audience=item.audience,
            character_id=item.character_id,
            content=item.content,
            revision=item.revision,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in summaries
    ]


@router.patch(
    "/campaigns/{campaign_id}/characters/{character_id}/hp",
    response_model=CampaignPlayState,
)
async def update_hp(
    campaign_id: str,
    character_id: str,
    payload: HpUpdate,
    session: DatabaseSession,
) -> CampaignPlayState:
    game_session = await CampaignService(session).update_campaign_hp(
        campaign_id, character_id, payload
    )
    await get_session_event_hub().publish("hp.changed", game_session.id)
    return to_play_state(game_session)


def to_skill_check_view(check) -> SkillCheckView:
    return SkillCheckView(
        id=check.id,
        campaign_id=check.campaign_id,
        character_id=check.character_id,
        character_name=check.character.name,
        skill=check.skill,
        modifier_snapshot=check.modifier_snapshot,
        roll_mode=check.roll_mode,
        die_one=check.die_one,
        die_two=check.die_two,
        selected_die=check.selected_die,
        total=check.total,
        dc=check.dc,
        system_outcome=check.system_outcome,
        dm_adjudication=check.dm_adjudication,
        reason=check.reason,
        status=check.status,
        void_reason=check.void_reason,
        created_at=check.created_at,
        adjudicated_at=check.adjudicated_at,
    )


@router.get("/campaigns/{campaign_id}/skills", response_model=list[CampaignSkillMemberView])
async def list_campaign_skills(
    campaign_id: str, session: DatabaseSession
) -> list[CampaignSkillMemberView]:
    values = await SkillCheckService(session).list_campaign_skills(campaign_id)
    return [
        CampaignSkillMemberView(
            character_id=character.id,
            name=character.name,
            modifiers=modifiers,
        )
        for character, modifiers in values
    ]


@router.get("/campaigns/{campaign_id}/skill-checks", response_model=list[SkillCheckView])
async def list_skill_checks(campaign_id: str, session: DatabaseSession) -> list[SkillCheckView]:
    checks = await SkillCheckService(session).list(campaign_id)
    return [to_skill_check_view(item) for item in checks]


@router.post(
    "/campaigns/{campaign_id}/skill-checks",
    response_model=SkillCheckView,
    status_code=status.HTTP_201_CREATED,
)
async def create_skill_check(
    campaign_id: str, payload: SkillCheckCreate, session: DatabaseSession
) -> SkillCheckView:
    check = await SkillCheckService(session).create(campaign_id, payload)
    await get_session_event_hub().publish("skill_check.created", check.session_id)
    return to_skill_check_view(check)


@router.post("/skill-checks/{check_id}:adjudicate", response_model=SkillCheckView)
async def adjudicate_skill_check(
    check_id: str, payload: SkillCheckAdjudicate, session: DatabaseSession
) -> SkillCheckView:
    check = await SkillCheckService(session).adjudicate(check_id, payload)
    await get_session_event_hub().publish("skill_check.adjudicated", check.session_id)
    return to_skill_check_view(check)


@router.post("/skill-checks/{check_id}:void", response_model=SkillCheckView)
async def void_skill_check(
    check_id: str, payload: SkillCheckVoid, session: DatabaseSession
) -> SkillCheckView:
    check = await SkillCheckService(session).void(check_id, payload)
    await get_session_event_hub().publish("skill_check.voided", check.session_id)
    return to_skill_check_view(check)

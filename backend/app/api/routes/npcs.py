from fastapi import APIRouter, status

from backend.app.api.dependencies import DatabaseSession
from backend.app.api.schemas.npcs import NpcCreate, NpcUpdate, NpcView
from backend.app.db.models import CampaignNpc
from backend.app.services.npc_service import NpcService

router = APIRouter(tags=["campaign-npcs"])


def view(npc: CampaignNpc) -> NpcView:
    return NpcView.model_validate(npc, from_attributes=True)


@router.get("/campaigns/{campaign_id}/npcs", response_model=list[NpcView])
async def list_npcs(campaign_id: str, session: DatabaseSession) -> list[NpcView]:
    return [view(item) for item in await NpcService(session).list(campaign_id)]


@router.post("/campaigns/{campaign_id}/npcs:extract", response_model=list[NpcView])
async def extract_npcs(campaign_id: str, session: DatabaseSession) -> list[NpcView]:
    return [view(item) for item in await NpcService(session).extract(campaign_id)]


@router.post(
    "/campaigns/{campaign_id}/npcs",
    response_model=NpcView,
    status_code=status.HTTP_201_CREATED,
)
async def create_npc(
    campaign_id: str, payload: NpcCreate, session: DatabaseSession
) -> NpcView:
    return view(await NpcService(session).create(campaign_id, payload))


@router.patch("/npcs/{npc_id}", response_model=NpcView)
async def update_npc(npc_id: str, payload: NpcUpdate, session: DatabaseSession) -> NpcView:
    return view(await NpcService(session).update(npc_id, payload))


@router.delete("/npcs/{npc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_npc(npc_id: str, session: DatabaseSession) -> None:
    await NpcService(session).delete(npc_id)

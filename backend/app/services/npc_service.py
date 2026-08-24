from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.npc_agent import DeepSeekNpcAgent, NpcCard
from backend.app.api.schemas.npcs import NpcCreate, NpcUpdate
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.db.models import CampaignNpc
from backend.app.services.campaign_service import CampaignService

logger = logging.getLogger(__name__)

SOURCE_AUTO = "AUTO"
SOURCE_DM = "DM"

_CARD_FIELDS = (
    "role",
    "personality",
    "ideal",
    "bond",
    "flaw",
    "knows",
    "wants",
    "voice",
)


class NpcService:
    """NPC cards are extracted once, then owned by the DM."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def list(self, campaign_id: str) -> list[CampaignNpc]:
        await CampaignService(self.session).get(campaign_id)
        return list(
            await self.session.scalars(
                select(CampaignNpc)
                .where(CampaignNpc.campaign_id == campaign_id)
                .order_by(CampaignNpc.name)
            )
        )

    async def get(self, npc_id: str) -> CampaignNpc:
        npc = await self.session.get(CampaignNpc, npc_id)
        if npc is None:
            raise NotFoundError("Campaign NPC", npc_id)
        return npc

    async def extract(self, campaign_id: str) -> list[CampaignNpc]:
        """Re-read the module and refresh the auto-extracted cards.

        Cards the DM created or edited are left alone: extraction is a starting
        point, not an authority.
        """
        campaign = await CampaignService(self.session).get(campaign_id)
        module = (campaign.module_content or campaign.dm_guide).strip()
        if not module:
            raise ConflictError("MODULE_CONTENT_REQUIRED", "提取 NPC 前必须先填写模组内容。")
        if not self.settings.dm_agent_is_configured:
            raise ConflictError("DM_AGENT_NOT_CONFIGURED", "AI DM 尚未配置，无法提取 NPC。")

        existing = {npc.name: npc for npc in await self.list(campaign_id)}
        protected = {name for name, npc in existing.items() if npc.source == SOURCE_DM}

        try:
            extraction = await DeepSeekNpcAgent(self.settings).extract(module)
        except Exception as error:
            logger.exception("NPC extraction failed: campaign_id=%s", campaign_id)
            raise ConflictError("NPC_EXTRACTION_FAILED", "NPC 提取失败，请重试。") from error

        seen: set[str] = set()
        for card in extraction.output.npcs:
            name = card.name.strip()
            if not name or name in protected or name in seen:
                continue
            seen.add(name)
            npc = existing.get(name)
            if npc is None:
                npc = CampaignNpc(campaign_id=campaign_id, name=name, source=SOURCE_AUTO)
                self.session.add(npc)
            self._apply_card(npc, card)
            npc.revision = (npc.revision or 0) + 1

        # Auto cards for names the module no longer mentions are stale.
        for name, npc in existing.items():
            if npc.source == SOURCE_AUTO and name not in seen:
                await self.session.delete(npc)

        await self.session.commit()
        return await self.list(campaign_id)

    async def create(self, campaign_id: str, payload: NpcCreate) -> CampaignNpc:
        await CampaignService(self.session).get(campaign_id)
        duplicate = await self.session.scalar(
            select(CampaignNpc).where(
                CampaignNpc.campaign_id == campaign_id,
                CampaignNpc.name == payload.name.strip(),
            )
        )
        if duplicate is not None:
            raise ConflictError("NPC_NAME_TAKEN", "这个战役里已经有同名 NPC 了。")
        npc = CampaignNpc(
            campaign_id=campaign_id, name=payload.name.strip(), source=SOURCE_DM
        )
        self._apply_card(npc, payload)
        self.session.add(npc)
        await self.session.commit()
        return npc

    async def update(self, npc_id: str, payload: NpcUpdate) -> CampaignNpc:
        npc = await self.get(npc_id)
        if npc.revision != payload.revision:
            raise ConflictError("NPC_REVISION_CONFLICT", "这张 NPC 卡已被更新，请刷新后重试。")
        if payload.name is not None:
            npc.name = payload.name.strip()
        self._apply_card(npc, payload, skip_none=True)
        # A hand-edited card is no longer overwritten by re-extraction.
        npc.source = SOURCE_DM
        npc.revision += 1
        await self.session.commit()
        return npc

    async def delete(self, npc_id: str) -> None:
        npc = await self.get(npc_id)
        await self.session.delete(npc)
        await self.session.commit()

    @staticmethod
    def _apply_card(
        npc: CampaignNpc, card: NpcCard | NpcCreate | NpcUpdate, *, skip_none: bool = False
    ) -> None:
        for field_name in _CARD_FIELDS:
            value = getattr(card, field_name, None)
            if value is None:
                if not skip_none:
                    setattr(npc, field_name, "")
                continue
            setattr(npc, field_name, str(value).strip())

from datetime import datetime

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import SummaryAudience


class CampaignSummaryView(ApiSchema):
    id: str
    campaign_id: str
    audience: SummaryAudience
    character_id: str | None
    content: str
    revision: int
    created_at: datetime
    updated_at: datetime

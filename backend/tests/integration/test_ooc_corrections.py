from pathlib import Path
from uuid import uuid4

from httpx import AsyncClient

from backend.tests.integration.test_stage_one_flow import configure_sheet, create_character


async def test_ooc_replaces_latest_dm_message_in_effective_timeline(
    api_client: AsyncClient, tmp_path: Path
) -> None:
    character = await create_character(api_client, "艾拉")
    await configure_sheet(api_client, tmp_path, str(character["id"]), "艾拉")
    campaign = (
        await api_client.post(
            "/api/v1/campaigns", json={"name": "OOC 测试", "characterIds": [character["id"]]}
        )
    ).json()
    activation = await api_client.post(f"/api/v1/campaigns/{campaign['id']}:activate")
    assert activation.status_code == 200
    game_session = (
        await api_client.post(
            f"/api/v1/campaigns/{campaign['id']}/sessions", json={"title": "第一节"}
        )
    ).json()
    original = await api_client.post(
        f"/api/v1/sessions/{game_session['id']}/messages",
        json={
            "content": "走廊里有三扇门。",
            "audience": "PUBLIC",
            "clientRequestId": str(uuid4()),
        },
    )
    assert original.status_code == 201
    correction = await api_client.post(
        f"/api/v1/sessions/{game_session['id']}/messages:ooc",
        json={
            "targetMessageId": original.json()["message"]["id"],
            "correction": "更正：这里只有两扇门。",
            "replacementContent": "走廊里只有两扇门。",
            "clientRequestId": str(uuid4()),
        },
    )
    assert correction.status_code == 200
    effective = await api_client.get(f"/api/v1/sessions/{game_session['id']}/messages")
    assert effective.status_code == 200
    messages = effective.json()
    assert len(messages) == 1
    assert messages[0]["content"] == "走廊里只有两扇门。"
    assert messages[0]["isOocCorrected"] is True
    assert messages[0]["oocCorrectionNote"] == "更正：这里只有两扇门。"

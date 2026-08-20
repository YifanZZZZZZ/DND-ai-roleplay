from pathlib import Path
from uuid import uuid4

from httpx import AsyncClient

from backend.tests.integration.test_stage_one_flow import configure_sheet, create_character


async def test_private_message_keeps_a_recipient_snapshot(
    api_client: AsyncClient, tmp_path: Path
) -> None:
    first = await create_character(api_client, "艾拉")
    second = await create_character(api_client, "布兰")
    await configure_sheet(api_client, tmp_path, str(first["id"]), "艾拉")
    await configure_sheet(api_client, tmp_path, str(second["id"]), "布兰")

    campaign = (
        await api_client.post(
            "/api/v1/campaigns",
            json={"name": "私语测试", "characterIds": [first["id"], second["id"]]},
        )
    ).json()
    assert (
        await api_client.post(f"/api/v1/campaigns/{campaign['id']}:activate")
    ).status_code == 200
    game_session = (
        await api_client.post(
            f"/api/v1/campaigns/{campaign['id']}/sessions", json={"title": "密谈"}
        )
    ).json()

    message = await api_client.post(
        f"/api/v1/sessions/{game_session['id']}/messages",
        json={
            "content": "只有艾拉注意到壁炉后的暗门。",
            "audience": "PRIVATE",
            "recipientCharacterIds": [first["id"]],
            "clientRequestId": str(uuid4()),
        },
    )
    assert message.status_code == 201
    assert [item["characterId"] for item in message.json()["message"]["recipients"]] == [
        first["id"]
    ]

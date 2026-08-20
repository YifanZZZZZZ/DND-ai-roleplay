from pathlib import Path
from uuid import uuid4

from httpx import AsyncClient
from openpyxl import Workbook


def build_character_sheet(path: Path, character_name: str) -> None:
    workbook = Workbook()
    main = workbook.active
    main.title = "主要"
    origin = workbook.create_sheet("起源")
    workbook.create_sheet("背包")
    spells = workbook.create_sheet("法术大全")

    main["A1"] = "DND 5E2024 人物卡<悲灵v1.0.0>"
    main["E3"] = character_name
    main["E6"] = "魔契师"
    main["I6"] = "咒剑"
    main["T6"] = "影灵"
    main["AX17"] = "契约魔法"
    main["BC17"] = "角色能够借助契约施展魔法。"
    main["BT30"] = "鸦后的祝福"
    main["BZ30"] = "角色可以短暂穿越阴影。"
    main["BU43"] = "健壮"
    main["BZ43"] = "角色有着异于常人的生命力。"
    main["Q68"] = "魔能爆"
    main["L31"] = "鳞甲"
    main["V31"] = "穿戴时行动较为沉重。"

    origin["E5"] = "堕影冥界"
    origin["E6"] = "城市猎人"
    origin["B24"] = "通用语"
    origin["B31"] = "赌具"

    spells["A2"] = "法术名"
    spells["C2"] = "学派"
    spells["F2"] = "施法时间"
    spells["G2"] = "施法距离"
    spells["M2"] = "法术详述"
    spells["A3"] = "魔能爆"
    spells["C3"] = "塑能"
    spells["F3"] = "动作"
    spells["G3"] = "远距离"
    spells["M3"] = "角色释放一束爆裂的魔法能量。"

    workbook.save(path)
    workbook.close()


async def create_character(client: AsyncClient, name: str, max_hp: int = 30) -> dict[str, object]:
    response = await client.post(
        "/api/v1/characters",
        json={"name": name, "roleplayPrompt": f"你是{name}。", "maxHp": max_hp},
    )
    assert response.status_code == 201
    return response.json()


async def configure_sheet(
    client: AsyncClient, tmp_path: Path, character_id: str, character_name: str
) -> None:
    sheet_path = tmp_path / f"{character_name}.xlsx"
    build_character_sheet(sheet_path, character_name)
    with sheet_path.open("rb") as source:
        response = await client.post(
            f"/api/v1/characters/{character_id}/sheet-versions:preview",
            files={
                "file": (
                    sheet_path.name,
                    source,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 201
    preview = response.json()
    assert preview["snapshot"]["characterName"] == character_name
    assert preview["snapshot"]["species"] == "影灵"
    assert len(preview["snapshot"]["classFeatures"]) == 1
    assert len(preview["snapshot"]["spells"]) == 1

    activation = await client.post(
        f"/api/v1/characters/{character_id}/sheet-versions/{preview['versionId']}:activate"
    )
    assert activation.status_code == 200


async def test_character_sheet_campaign_session_and_hp_flow(
    api_client: AsyncClient, tmp_path: Path
) -> None:
    character = await create_character(api_client, "赛蕾妮", max_hp=30)
    character_id = str(character["id"])
    await configure_sheet(api_client, tmp_path, character_id, "赛蕾妮")

    campaign_response = await api_client.post(
        "/api/v1/campaigns",
        json={"name": "鸦影之路", "description": "测试战役", "characterIds": [character_id]},
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    activation = await api_client.post(f"/api/v1/campaigns/{campaign['id']}:activate")
    assert activation.status_code == 200
    assert activation.json()["lifecycleStatus"] == "ACTIVE"

    session_response = await api_client.post(
        f"/api/v1/campaigns/{campaign['id']}/sessions", json={"title": "初入迷雾"}
    )
    assert session_response.status_code == 201
    game_session = session_response.json()
    assert game_session["runtimeStatus"] == "IDLE"
    assert game_session["hpStates"][0]["currentHp"] == 30

    request_id = str(uuid4())
    dm_message = await api_client.post(
        f"/api/v1/sessions/{game_session['id']}/messages",
        json={
            "content": "浓雾沿着石板路缓缓漫来。",
            "audience": "PUBLIC",
            "clientRequestId": request_id,
        },
    )
    assert dm_message.status_code == 201
    assert dm_message.json()["message"]["sequenceNo"] == 1
    assert dm_message.json()["message"]["recipients"][0]["characterId"] == character_id
    assert dm_message.json()["runtime"]["status"] == "IDLE"

    retried_message = await api_client.post(
        f"/api/v1/sessions/{game_session['id']}/messages",
        json={
            "content": "浓雾沿着石板路缓缓漫来。",
            "audience": "PUBLIC",
            "clientRequestId": request_id,
        },
    )
    assert retried_message.status_code == 201
    assert retried_message.json()["message"]["id"] == dm_message.json()["message"]["id"]

    stopped = await api_client.post(f"/api/v1/sessions/{game_session['id']}/runtime:stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "IDLE"

    listed_messages = await api_client.get(f"/api/v1/sessions/{game_session['id']}/messages")
    assert listed_messages.status_code == 200
    assert len(listed_messages.json()) == 1

    character_detail = await api_client.get(f"/api/v1/characters/{character_id}")
    revision = character_detail.json()["revision"]
    hp_reset = await api_client.patch(
        f"/api/v1/characters/{character_id}", json={"revision": revision, "maxHp": 42}
    )
    assert hp_reset.status_code == 200

    refreshed_session = await api_client.get(f"/api/v1/sessions/{game_session['id']}")
    assert refreshed_session.json()["hpStates"][0]["currentHp"] == 42
    assert refreshed_session.json()["hpStates"][0]["maxHp"] == 42

    hp_update = await api_client.patch(
        f"/api/v1/sessions/{game_session['id']}/characters/{character_id}/hp",
        json={"currentHp": 11},
    )
    assert hp_update.status_code == 200
    assert hp_update.json()["hpStates"][0]["currentHp"] == 11

    overlapping_session = await api_client.post(
        f"/api/v1/campaigns/{campaign['id']}/sessions", json={"title": "不应被创建"}
    )
    assert overlapping_session.status_code == 409
    assert overlapping_session.json()["errorCode"] == "ACTIVE_SESSION_EXISTS"

    ended = await api_client.post(f"/api/v1/sessions/{game_session['id']}:end")
    assert ended.status_code == 200
    assert ended.json()["status"] == "ENDED"

    next_session = await api_client.post(
        f"/api/v1/campaigns/{campaign['id']}/sessions", json={"title": "再次启程"}
    )
    assert next_session.status_code == 201
    assert next_session.json()["hpStates"][0]["currentHp"] == 11

    await api_client.post(f"/api/v1/sessions/{next_session.json()['id']}:end")
    completed = await api_client.post(f"/api/v1/campaigns/{campaign['id']}:complete")
    assert completed.status_code == 200
    assert completed.json()["lifecycleStatus"] == "COMPLETED"

    reopened = await api_client.post(f"/api/v1/campaigns/{campaign['id']}:reopen")
    assert reopened.status_code == 200
    assert reopened.json()["lifecycleStatus"] == "ACTIVE"


async def test_only_one_active_campaign(api_client: AsyncClient, tmp_path: Path) -> None:
    first = await create_character(api_client, "甲")
    second = await create_character(api_client, "乙")
    await configure_sheet(api_client, tmp_path, str(first["id"]), "甲")
    await configure_sheet(api_client, tmp_path, str(second["id"]), "乙")

    first_campaign = (
        await api_client.post(
            "/api/v1/campaigns",
            json={"name": "第一团", "characterIds": [first["id"]]},
        )
    ).json()
    second_campaign = (
        await api_client.post(
            "/api/v1/campaigns",
            json={"name": "第二团", "characterIds": [second["id"]]},
        )
    ).json()

    first_activation = await api_client.post(f"/api/v1/campaigns/{first_campaign['id']}:activate")
    second_activation = await api_client.post(f"/api/v1/campaigns/{second_campaign['id']}:activate")
    assert first_activation.status_code == 200
    assert second_activation.status_code == 409
    assert second_activation.json()["errorCode"] == "ACTIVE_CAMPAIGN_EXISTS"


async def test_incomplete_character_cannot_start_campaign(api_client: AsyncClient) -> None:
    character = await create_character(api_client, "未完成角色")
    campaign = (
        await api_client.post(
            "/api/v1/campaigns",
            json={"name": "未完成配置", "characterIds": [character["id"]]},
        )
    ).json()

    activation = await api_client.post(f"/api/v1/campaigns/{campaign['id']}:activate")
    assert activation.status_code == 400
    assert activation.json()["errorCode"] == "CHARACTER_CONFIGURATION_INCOMPLETE"

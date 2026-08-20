import createClient from "openapi-fetch";

import type { components, paths } from "./generated";

export type CharacterSummary = components["schemas"]["CharacterSummary"];
export type CharacterDetail = components["schemas"]["CharacterDetail"];
export type CharacterCreate = components["schemas"]["CharacterCreate"];
export type CampaignSummary = components["schemas"]["CampaignSummary"];
export type CampaignDetail = components["schemas"]["CampaignDetail"];
export type CampaignCreate = components["schemas"]["CampaignCreate"];
export type SessionDetail = components["schemas"]["SessionDetail"];
export type MessageView = components["schemas"]["MessageView"];
export type RuntimeState = components["schemas"]["RuntimeState"];
export type DmMessageCreate = components["schemas"]["DmMessageCreate"];
export type OocCorrectionCreate = components["schemas"]["OocCorrectionCreate"];
export type SheetPreview = components["schemas"]["SheetPreview"];
export type SheetActivation = components["schemas"]["SheetActivation"];
export type MemoryView = components["schemas"]["MemoryView"];

const client = createClient<paths>({ baseUrl: "" });

function messageFromError(error: unknown): string {
  if (typeof error === "object" && error !== null && "message" in error) {
    const message = Reflect.get(error, "message");
    if (typeof message === "string") return message;
  }
  return "请求失败，请稍后重试。";
}

function requireData<T>(data: T | undefined, error: unknown): T {
  if (data === undefined) throw new Error(messageFromError(error));
  return data;
}

export async function listCharacters(): Promise<CharacterSummary[]> {
  const { data, error } = await client.GET("/api/v1/characters");
  return requireData(data, error);
}

export async function createCharacter(payload: CharacterCreate): Promise<CharacterDetail> {
  const { data, error } = await client.POST("/api/v1/characters", { body: payload });
  return requireData(data, error);
}

export async function getCharacter(characterId: string): Promise<CharacterDetail> {
  const { data, error } = await client.GET("/api/v1/characters/{character_id}", {
    params: { path: { character_id: characterId } },
  });
  return requireData(data, error);
}

export async function updateCharacter(
  characterId: string,
  payload: components["schemas"]["CharacterUpdate"],
): Promise<CharacterDetail> {
  const { data, error } = await client.PATCH("/api/v1/characters/{character_id}", {
    params: { path: { character_id: characterId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function uploadAvatar(characterId: string, file: File): Promise<CharacterDetail> {
  const body = new FormData();
  body.set("file", file);
  const response = await fetch(`/api/v1/characters/${encodeURIComponent(characterId)}/avatar`, {
    method: "POST", body,
  });
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error(messageFromError(payload));
  return payload as CharacterDetail;
}

export async function listMemories(characterId: string): Promise<MemoryView[]> {
  const { data, error } = await client.GET("/api/v1/characters/{character_id}/memories", {
    params: { path: { character_id: characterId } },
  });
  return requireData(data, error);
}

export async function createMemory(
  characterId: string,
  content: string,
  pinned: boolean,
): Promise<MemoryView> {
  const { data, error } = await client.POST("/api/v1/characters/{character_id}/memories", {
    params: { path: { character_id: characterId } },
    body: { content, pinned },
  });
  return requireData(data, error);
}

export async function deleteMemory(characterId: string, memoryId: string): Promise<void> {
  const { error } = await client.DELETE("/api/v1/characters/{character_id}/memories/{memory_id}", {
    params: { path: { character_id: characterId, memory_id: memoryId } },
  });
  if (error) throw new Error(messageFromError(error));
}

export async function deleteCampaign(campaignId: string): Promise<void> {
  const { error } = await client.DELETE("/api/v1/campaigns/{campaign_id}", {
    params: { path: { campaign_id: campaignId } },
  });
  if (error) throw new Error(messageFromError(error));
}

export function exportUrl(kind: "campaign" | "character", id: string): string {
  return `/api/v1/${kind === "campaign" ? "campaigns" : "characters"}/${encodeURIComponent(id)}:export`;
}

export async function listCampaigns(): Promise<CampaignSummary[]> {
  const { data, error } = await client.GET("/api/v1/campaigns");
  return requireData(data, error);
}

export async function getCampaign(campaignId: string): Promise<CampaignDetail> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function createCampaign(payload: CampaignCreate): Promise<CampaignDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns", { body: payload });
  return requireData(data, error);
}

export async function replaceCampaignMemberships(
  campaignId: string,
  revision: number,
  characterIds: string[],
): Promise<CampaignDetail> {
  const { data, error } = await client.PUT("/api/v1/campaigns/{campaign_id}/memberships", {
    params: { path: { campaign_id: campaignId } },
    body: { revision, characterIds },
  });
  return requireData(data, error);
}

export async function activateCampaign(campaignId: string): Promise<CampaignDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}:activate", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function completeCampaign(campaignId: string): Promise<CampaignDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}:complete", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function reopenCampaign(campaignId: string): Promise<CampaignDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}:reopen", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function createSession(
  campaignId: string,
  title: string,
): Promise<SessionDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}/sessions", {
    params: { path: { campaign_id: campaignId } },
    body: { title },
  });
  return requireData(data, error);
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const { data, error } = await client.GET("/api/v1/sessions/{session_id}", {
    params: { path: { session_id: sessionId } },
  });
  return requireData(data, error);
}

export async function endSession(sessionId: string): Promise<SessionDetail> {
  const { data, error } = await client.POST("/api/v1/sessions/{session_id}:end", {
    params: { path: { session_id: sessionId } },
  });
  return requireData(data, error);
}

export async function updateSessionHp(
  sessionId: string,
  characterId: string,
  currentHp: number,
): Promise<SessionDetail> {
  const { data, error } = await client.PATCH(
    "/api/v1/sessions/{session_id}/characters/{character_id}/hp",
    {
      params: { path: { session_id: sessionId, character_id: characterId } },
      body: { currentHp },
    },
  );
  return requireData(data, error);
}

export async function listMessages(sessionId: string): Promise<MessageView[]> {
  const { data, error } = await client.GET("/api/v1/sessions/{session_id}/messages", {
    params: { path: { session_id: sessionId } },
  });
  return requireData(data, error);
}

export async function sendDmMessage(
  sessionId: string,
  payload: DmMessageCreate,
): Promise<components["schemas"]["DmMessageCommandResult"]> {
  const { data, error } = await client.POST("/api/v1/sessions/{session_id}/messages", {
    params: { path: { session_id: sessionId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function stopSessionRuntime(sessionId: string): Promise<RuntimeState> {
  const { data, error } = await client.POST("/api/v1/sessions/{session_id}/runtime:stop", {
    params: { path: { session_id: sessionId } },
  });
  return requireData(data, error);
}

export async function correctMessageWithOoc(
  sessionId: string,
  payload: OocCorrectionCreate,
): Promise<RuntimeState> {
  const { data, error } = await client.POST("/api/v1/sessions/{session_id}/messages:ooc", {
    params: { path: { session_id: sessionId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function previewCharacterSheet(
  characterId: string,
  file: File,
): Promise<SheetPreview> {
  const body = new FormData();
  body.set("file", file);
  const response = await fetch(
    `/api/v1/characters/${encodeURIComponent(characterId)}/sheet-versions:preview`,
    { method: "POST", body },
  );
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error(messageFromError(payload));
  return payload as SheetPreview;
}

export async function activateCharacterSheet(
  characterId: string,
  versionId: string,
): Promise<SheetActivation> {
  const { data, error } = await client.POST(
    "/api/v1/characters/{character_id}/sheet-versions/{version_id}:activate",
    { params: { path: { character_id: characterId, version_id: versionId } } },
  );
  return requireData(data, error);
}

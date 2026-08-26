import createClient from "openapi-fetch";

import type { components, paths } from "./generated";

export type CharacterSummary = components["schemas"]["CharacterSummary"];
export type CharacterDetail = components["schemas"]["CharacterDetail"];
export type CharacterCreate = components["schemas"]["CharacterCreate"];
export type CampaignSummary = components["schemas"]["CampaignSummary"];
export type CampaignDetail = components["schemas"]["CampaignDetail"];
export type CampaignCreate = components["schemas"]["CampaignCreate"];
export type CampaignPlayState = components["schemas"]["CampaignPlayState"];
export type MessageView = components["schemas"]["MessageView"];
export type RuntimeState = components["schemas"]["RuntimeState"];
export type DmMessageCreate = components["schemas"]["DmMessageCreate"];
export type OocCorrectionCreate = components["schemas"]["OocCorrectionCreate"];
export type SheetPreview = components["schemas"]["SheetPreview"];
export type SheetActivation = components["schemas"]["SheetActivation"];
export type MemoryView = components["schemas"]["MemoryView"];
export type SkillSetView = components["schemas"]["SkillSetView"];
export type CampaignSkillMemberView = components["schemas"]["CampaignSkillMemberView"];
export type SkillCheckView = components["schemas"]["SkillCheckView"];
export type SkillName = components["schemas"]["SkillName"];
export type RollMode = components["schemas"]["RollMode"];
export type DmDraftView = components["schemas"]["DmDraftView"];
export type CampaignSummaryView = components["schemas"]["CampaignSummaryView"];
export type CharacterAcquaintanceView = components["schemas"]["CharacterAcquaintanceView"];
export type CharacterSpellInput = components["schemas"]["CharacterSpellInput"];
export type CharacterSpellbookView = components["schemas"]["CharacterSpellbookView"];

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

export async function getSkillSet(characterId: string): Promise<SkillSetView> {
  const { data, error } = await client.GET("/api/v1/characters/{character_id}/skills", {
    params: { path: { character_id: characterId } },
  });
  return requireData(data, error);
}

export async function updateSkillSet(
  characterId: string,
  payload: components["schemas"]["SkillSetUpdate"],
): Promise<SkillSetView> {
  const { data, error } = await client.PUT("/api/v1/characters/{character_id}/skills", {
    params: { path: { character_id: characterId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function getSpellbook(characterId: string): Promise<CharacterSpellbookView> {
  const { data, error } = await client.GET("/api/v1/characters/{character_id}/spellbook", {
    params: { path: { character_id: characterId } },
  });
  return requireData(data, error);
}

export async function updateSpellbook(
  characterId: string,
  revision: number,
  spells: CharacterSpellInput[],
): Promise<CharacterSpellbookView> {
  const { data, error } = await client.PUT("/api/v1/characters/{character_id}/spellbook", {
    params: { path: { character_id: characterId } },
    body: { revision, spells },
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

export async function updateMemory(
  characterId: string,
  memoryId: string,
  payload: { content?: string; pinned?: boolean },
): Promise<MemoryView> {
  const { data, error } = await client.PATCH(
    "/api/v1/characters/{character_id}/memories/{memory_id}",
    { params: { path: { character_id: characterId, memory_id: memoryId } }, body: payload },
  );
  return requireData(data, error);
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

export async function listCampaignAcquaintances(
  campaignId: string,
): Promise<CharacterAcquaintanceView[]> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}/acquaintances", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function updateCampaign(
  campaignId: string,
  payload: components["schemas"]["CampaignUpdate"],
): Promise<CampaignDetail> {
  const { data, error } = await client.PATCH("/api/v1/campaigns/{campaign_id}", {
    params: { path: { campaign_id: campaignId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function activateCampaign(campaignId: string): Promise<CampaignDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}:activate", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function pauseCampaign(campaignId: string): Promise<CampaignDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}:pause", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function resumeCampaign(campaignId: string): Promise<CampaignDetail> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}:resume", {
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

export async function getCampaignPlayState(campaignId: string): Promise<CampaignPlayState> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}/play", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function updateCampaignHp(
  campaignId: string,
  characterId: string,
  currentHp: number,
): Promise<CampaignPlayState> {
  const { data, error } = await client.PATCH(
    "/api/v1/campaigns/{campaign_id}/characters/{character_id}/hp",
    {
      params: { path: { campaign_id: campaignId, character_id: characterId } },
      body: { currentHp },
    },
  );
  return requireData(data, error);
}

export async function listCampaignSkills(campaignId: string): Promise<CampaignSkillMemberView[]> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}/skills", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function listSkillChecks(campaignId: string): Promise<SkillCheckView[]> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}/skill-checks", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function listCampaignSummaries(campaignId: string): Promise<CampaignSummaryView[]> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}/summaries", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function createDmDraft(
  campaignId: string,
  payload: components["schemas"]["DmDraftCreate"],
): Promise<DmDraftView> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}/dm-drafts", {
    params: { path: { campaign_id: campaignId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function listDmDrafts(campaignId: string): Promise<DmDraftView[]> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}/dm-drafts", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function generateOpeningDraft(campaignId: string): Promise<DmDraftView> {
  const { data, error } = await client.POST(
    "/api/v1/campaigns/{campaign_id}/dm-drafts:generate-opening",
    { params: { path: { campaign_id: campaignId } } },
  );
  return requireData(data, error);
}

export async function updateDmDraft(
  draftId: string,
  payload: components["schemas"]["DmDraftUpdate"],
): Promise<DmDraftView> {
  const { data, error } = await client.PATCH("/api/v1/dm-drafts/{draft_id}", {
    params: { path: { draft_id: draftId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function publishDmDraft(draftId: string): Promise<{ draft: DmDraftView; message: MessageView }> {
  const { data, error } = await client.POST("/api/v1/dm-drafts/{draft_id}:publish", {
    params: { path: { draft_id: draftId } },
  });
  return requireData(data, error);
}

export async function discardDmDraft(draftId: string): Promise<DmDraftView> {
  const { data, error } = await client.POST("/api/v1/dm-drafts/{draft_id}:discard", {
    params: { path: { draft_id: draftId } },
  });
  return requireData(data, error);
}

export async function createSkillCheck(
  campaignId: string,
  payload: components["schemas"]["SkillCheckCreate"],
): Promise<SkillCheckView> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}/skill-checks", {
    params: { path: { campaign_id: campaignId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function adjudicateSkillCheck(
  checkId: string,
  outcome: components["schemas"]["SkillCheckDmAdjudication"],
): Promise<SkillCheckView> {
  const { data, error } = await client.POST("/api/v1/skill-checks/{check_id}:adjudicate", {
    params: { path: { check_id: checkId } },
    body: { outcome },
  });
  return requireData(data, error);
}

export async function voidSkillCheck(checkId: string, reason: string): Promise<SkillCheckView> {
  const { data, error } = await client.POST("/api/v1/skill-checks/{check_id}:void", {
    params: { path: { check_id: checkId } },
    body: { reason },
  });
  return requireData(data, error);
}

export async function listMessages(campaignId: string): Promise<MessageView[]> {
  const { data, error } = await client.GET("/api/v1/campaigns/{campaign_id}/messages", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function sendDmMessage(
  campaignId: string,
  payload: DmMessageCreate,
): Promise<components["schemas"]["DmMessageCommandResult"]> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}/messages", {
    params: { path: { campaign_id: campaignId } },
    body: payload,
  });
  return requireData(data, error);
}

export async function stopCampaignRuntime(campaignId: string): Promise<RuntimeState> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}/runtime:stop", {
    params: { path: { campaign_id: campaignId } },
  });
  return requireData(data, error);
}

export async function retryCampaignRuntime(campaignId: string): Promise<RuntimeState> {
  const response = await fetch(`/api/v1/campaigns/${encodeURIComponent(campaignId)}/runtime:retry`, {
    method: "POST",
  });
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error(messageFromError(payload));
  return payload as RuntimeState;
}

export async function correctMessageWithOoc(
  campaignId: string,
  payload: OocCorrectionCreate,
): Promise<RuntimeState> {
  const { data, error } = await client.POST("/api/v1/campaigns/{campaign_id}/messages:ooc", {
    params: { path: { campaign_id: campaignId } },
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
  spellbook: CharacterSpellInput[],
): Promise<SheetActivation> {
  const { data, error } = await client.POST(
    "/api/v1/characters/{character_id}/sheet-versions/{version_id}:activate",
    {
      params: { path: { character_id: characterId, version_id: versionId } },
      body: { spellbook },
    },
  );
  return requireData(data, error);
}

// --- Campaign NPC cards -----------------------------------------------------
// Hand-written until `npm run generate:api` folds these paths into generated.ts.

export interface NpcView {
  id: string;
  campaignId: string;
  name: string;
  role: string;
  personality: string;
  ideal: string;
  bond: string;
  flaw: string;
  knows: string;
  wants: string;
  voice: string;
  source: string;
  revision: number;
  createdAt: string;
  updatedAt: string;
}

export type NpcFields = Pick<
  NpcView,
  "name" | "role" | "personality" | "ideal" | "bond" | "flaw" | "knows" | "wants" | "voice"
>;

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: init?.body ? { "content-type": "application/json" } : undefined,
  });
  if (response.status === 204) return undefined as T;
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error(messageFromError(payload));
  return payload as T;
}

export async function listNpcs(campaignId: string): Promise<NpcView[]> {
  return requestJson<NpcView[]>(`/api/v1/campaigns/${encodeURIComponent(campaignId)}/npcs`);
}

export async function extractNpcs(campaignId: string): Promise<NpcView[]> {
  return requestJson<NpcView[]>(
    `/api/v1/campaigns/${encodeURIComponent(campaignId)}/npcs:extract`,
    { method: "POST" },
  );
}

export async function createNpc(
  campaignId: string,
  payload: Partial<NpcFields> & { name: string },
): Promise<NpcView> {
  return requestJson<NpcView>(`/api/v1/campaigns/${encodeURIComponent(campaignId)}/npcs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateNpc(
  npcId: string,
  payload: Partial<NpcFields> & { revision: number },
): Promise<NpcView> {
  return requestJson<NpcView>(`/api/v1/npcs/${encodeURIComponent(npcId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteNpc(npcId: string): Promise<void> {
  await requestJson<void>(`/api/v1/npcs/${encodeURIComponent(npcId)}`, { method: "DELETE" });
}

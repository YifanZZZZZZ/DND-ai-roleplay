export const queryKeys = {
  characters: ["characters"] as const,
  memories: (characterId: string) => ["characters", characterId, "memories"] as const,
  campaigns: ["campaigns"] as const,
  campaign: (campaignId: string) => ["campaigns", campaignId] as const,
  session: (sessionId: string) => ["sessions", sessionId] as const,
  messages: (sessionId: string) => ["sessions", sessionId, "messages"] as const,
};

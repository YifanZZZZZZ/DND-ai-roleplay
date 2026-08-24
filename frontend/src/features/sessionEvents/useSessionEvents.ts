import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "../../api/queryKeys";

export function useSessionEvents(campaignId: string | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!campaignId) return;
    const events = new EventSource(`/api/v1/campaigns/${encodeURIComponent(campaignId)}/events`);
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.play(campaignId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.messages(campaignId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.acquaintances(campaignId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dmDrafts(campaignId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
    };

    events.addEventListener("message.created", refresh);
    events.addEventListener("runtime.changed", refresh);
    events.addEventListener("hp.changed", refresh);
    events.addEventListener("dm_draft.changed", refresh);
    events.addEventListener("dm_draft.failed", refresh);
    return () => events.close();
  }, [queryClient, campaignId]);
}

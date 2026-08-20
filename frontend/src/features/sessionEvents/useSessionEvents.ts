import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "../../api/queryKeys";

export function useSessionEvents(sessionId: string | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!sessionId) return;
    const events = new EventSource(`/api/v1/sessions/${encodeURIComponent(sessionId)}/events`);
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.messages(sessionId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
    };

    events.addEventListener("message.created", refresh);
    events.addEventListener("runtime.changed", refresh);
    events.addEventListener("hp.changed", refresh);
    return () => events.close();
  }, [queryClient, sessionId]);
}

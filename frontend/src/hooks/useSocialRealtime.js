import { useEffect, useRef } from "react";
import api, { getWsBaseUrl } from "../services/api";

export const SOCIAL_REALTIME_EVENT_NAME = "chithi:social-realtime";

export default function useSocialRealtime(onEvent, enabled = true) {
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled) return undefined;

    let socket = null;
    let cancelled = false;

    const connect = async () => {
      try {
        const tokenResp = await api.get("/api/chat/ws-token/");
        const wsToken = tokenResp?.data?.ws_token;
        if (!wsToken || cancelled) return;

        socket = new WebSocket(`${getWsBaseUrl()}/ws/social/?ws_token=${encodeURIComponent(wsToken)}`);

        socket.onmessage = (evt) => {
          try {
            const payload = JSON.parse(evt.data);
            if (payload?.type !== "social_event") return;

            onEventRef.current?.(payload);
            if (typeof window !== "undefined") {
              window.dispatchEvent(new CustomEvent(SOCIAL_REALTIME_EVENT_NAME, { detail: payload }));
            }
          } catch (err) {
            console.error("Failed to parse social realtime event", err);
          }
        };
      } catch (err) {
        console.error("Failed to connect social realtime socket", err);
      }
    };

    connect();

    return () => {
      cancelled = true;
      try {
        socket?.close();
      } catch (_) {
        // no-op
      }
    };
  }, [enabled]);
}

import { useCallback, useEffect, useState } from "react";
import { getUnreadNotificationCount } from "../services/api";
import useSocialRealtime from "./useSocialRealtime";
import { NOTIFICATION_COUNT_EVENT_NAME } from "../utils/notificationEvents";

export default function useNotificationCount(enabled = true) {
  const [unreadCount, setUnreadCount] = useState(0);

  const refreshUnreadCount = useCallback(async () => {
    if (!enabled) return;
    try {
      const { data } = await getUnreadNotificationCount();
      setUnreadCount(Number(data?.unread_count || 0));
    } catch {
      // Keep last known value.
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return undefined;
    refreshUnreadCount();
  }, [enabled, refreshUnreadCount]);

  const handleRealtimeEvent = useCallback((payload) => {
    const eventName = payload?.event;
    if (
      eventName === "notification_created" ||
      eventName === "notification_read" ||
      eventName === "notification_read_all"
    ) {
      if (typeof payload.unread_count === "number") {
        setUnreadCount(payload.unread_count);
      } else {
        refreshUnreadCount();
      }
    }
  }, [refreshUnreadCount]);

  useSocialRealtime(handleRealtimeEvent, enabled);

  useEffect(() => {
    if (!enabled) return undefined;
    const handler = (event) => {
      const detail = event?.detail || {};
      if (typeof detail.unread_count === "number") {
        setUnreadCount(detail.unread_count);
      } else {
        refreshUnreadCount();
      }
    };
    window.addEventListener(NOTIFICATION_COUNT_EVENT_NAME, handler);
    return () => window.removeEventListener(NOTIFICATION_COUNT_EVENT_NAME, handler);
  }, [enabled, refreshUnreadCount]);

  return {
    unreadCount,
    refreshUnreadCount,
  };
}

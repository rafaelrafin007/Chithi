export const NOTIFICATION_COUNT_EVENT_NAME = "chithi:notification-count-sync";

export function dispatchNotificationCountSync(payload = {}) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent(NOTIFICATION_COUNT_EVENT_NAME, {
      detail: payload,
    })
  );
}

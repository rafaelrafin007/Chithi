import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import SocialNav from "../components/SocialNav";
import { getNotifications, markAllNotificationsRead, markNotificationRead } from "../services/api";
import useSocialRealtime from "../hooks/useSocialRealtime";
import { dispatchNotificationCountSync } from "../utils/notificationEvents";

function normalizePaged(payload) {
  if (Array.isArray(payload)) return { results: payload, next: null };
  if (payload && Array.isArray(payload.results)) {
    return { results: payload.results, next: payload.next || null };
  }
  return { results: [], next: null };
}

function formatTime(timestamp) {
  if (!timestamp) return "";
  return new Date(timestamp).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildMessage(notification) {
  const actor = notification?.actor?.display_name || notification?.actor?.username || "Someone";
  if (notification.type === "follow") return `${actor} followed you`;
  if (notification.type === "post_like") return `${actor} liked your post`;
  if (notification.type === "post_comment") return `${actor} commented on your post`;
  return `${actor} sent an update`;
}

export default function NotificationPage() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [nextPage, setNextPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const theme = localStorage.getItem("theme") || "dark";
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
  }, []);

  const loadNotifications = useCallback(async ({ page = 1, append = false } = {}) => {
    if (!append) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const { data } = await getNotifications({ page });
      const normalized = normalizePaged(data);
      setItems((prev) => (append ? [...prev, ...normalized.results] : normalized.results));
      setNextPage(normalized.next);
    } catch (err) {
      setError(err?.response?.data?.detail || "Unable to load notifications.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadNotifications({ page: 1, append: false });
  }, [loadNotifications]);

  const unreadCount = useMemo(() => items.filter((item) => !item.is_read).length, [items]);

  useEffect(() => {
    dispatchNotificationCountSync({ unread_count: unreadCount });
  }, [unreadCount]);

  const handleRealtimeEvent = useCallback((payload) => {
    const eventName = payload?.event;
    if (!eventName) return;

    if (eventName === "notification_created" && payload.notification) {
      setItems((prev) => {
        const exists = prev.some((item) => item.id === payload.notification.id);
        if (exists) {
          return prev.map((item) => (item.id === payload.notification.id ? payload.notification : item));
        }
        return [payload.notification, ...prev];
      });
      return;
    }

    if (eventName === "notification_read" && payload.notification_id) {
      setItems((prev) =>
        prev.map((item) => (item.id === payload.notification_id ? { ...item, is_read: true } : item))
      );
      return;
    }

    if (eventName === "notification_read_all") {
      setItems((prev) => prev.map((item) => ({ ...item, is_read: true })));
    }
  }, []);

  useSocialRealtime(handleRealtimeEvent, true);

  const handleMarkOne = async (notificationId) => {
    setItems((prev) => prev.map((item) => (item.id === notificationId ? { ...item, is_read: true } : item)));
    try {
      await markNotificationRead(notificationId);
    } catch (err) {
      setItems((prev) => prev.map((item) => (item.id === notificationId ? { ...item, is_read: false } : item)));
      setError(err?.response?.data?.detail || "Failed to mark notification as read.");
    }
  };

  const handleMarkAll = async () => {
    if (!unreadCount || markingAll) return;
    setMarkingAll(true);
    setItems((prev) => prev.map((item) => ({ ...item, is_read: true })));
    try {
      await markAllNotificationsRead();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to mark all notifications as read.");
      await loadNotifications({ page: 1, append: false });
    } finally {
      setMarkingAll(false);
    }
  };

  const loadMore = async () => {
    if (!nextPage || loadingMore) return;
    try {
      const url = new URL(nextPage);
      const page = Number(url.searchParams.get("page") || "1");
      await loadNotifications({ page, append: true });
    } catch {
      await loadNotifications({ page: 1, append: true });
    }
  };

  return (
    <div className="social-page">
      <div className="social-shell">
        <div className="social-top">
          <div>
            <div className="social-kicker">Chithi Social</div>
            <h2>Notifications</h2>
          </div>
          <SocialNav />
        </div>

        <section className="social-card">
          <div className="notification-toolbar">
            <div className="notification-unread">{unreadCount} unread</div>
            <button
              type="button"
              className="social-action-btn"
              onClick={handleMarkAll}
              disabled={!unreadCount || markingAll}
            >
              {markingAll ? "Updating..." : "Mark all as read"}
            </button>
          </div>
        </section>

        {loading ? (
          <div className="social-state">Loading notifications...</div>
        ) : error ? (
          <div className="social-state error">
            <p>{error}</p>
            <button type="button" className="social-action-btn" onClick={() => loadNotifications({ page: 1 })}>
              Retry
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="social-state">No notifications yet.</div>
        ) : (
          <div className="social-list">
            {items.map((item) => (
              <article key={item.id} className={`social-card notification-card ${item.is_read ? "read" : "unread"}`}>
                <div className="notification-main">
                  <button
                    type="button"
                    className="notification-actor-link"
                    onClick={() => item.actor?.username && nav(`/profile/${item.actor.username}`)}
                  >
                    {item.actor?.avatar_url ? (
                      <img src={item.actor.avatar_url} alt={item.actor.display_name || item.actor.username} className="post-avatar" />
                    ) : (
                      <div className="post-avatar fallback">
                        {(item.actor?.display_name || item.actor?.username || "U").charAt(0).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <div>{buildMessage(item)}</div>
                      <div className="post-time">{formatTime(item.created_at)}</div>
                    </div>
                  </button>
                </div>
                <div className="notification-actions">
                  {!item.is_read && (
                    <button type="button" className="social-link-btn" onClick={() => handleMarkOne(item.id)}>
                      Mark read
                    </button>
                  )}
                  {item.target_post_id && (
                    <button type="button" className="social-link-btn" onClick={() => nav("/feed")}>
                      View post
                    </button>
                  )}
                </div>
              </article>
            ))}
            {nextPage && (
              <button type="button" className="social-load-btn" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? "Loading..." : "Load more"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

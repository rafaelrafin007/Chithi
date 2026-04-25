import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import useNotificationCount from "../hooks/useNotificationCount";

const ICONS = {
  chat: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 6.5h14a2 2 0 0 1 2 2V16a2 2 0 0 1-2 2h-8l-4.5 3V18H5a2 2 0 0 1-2-2V8.5a2 2 0 0 1 2-2Z" />
    </svg>
  ),
  feed: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1v-9.5Z" />
    </svg>
  ),
  friends: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M16.5 11.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM8 12.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
      <path d="M2.5 20c0-3 2.6-5.5 5.5-5.5s5.5 2.5 5.5 5.5M12.5 20c0-2.2 1.8-4 4-4s4 1.8 4 4" />
    </svg>
  ),
  notifications: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4.5a5 5 0 0 0-5 5v3.2c0 .7-.2 1.4-.6 2L5 17h14l-1.4-2.3a4 4 0 0 1-.6-2V9.5a5 5 0 0 0-5-5Z" />
      <path d="M9.5 19a2.5 2.5 0 0 0 5 0" />
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 12.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
      <path d="M4 20a8 8 0 0 1 16 0" />
    </svg>
  ),
  search: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
  ),
};

export default function SocialNav({ className = "", variant = "default" }) {
  const nav = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { unreadCount } = useNotificationCount(!!user?.id);

  const profileIdentifier = user?.username || user?.id;
  const iconOnly = variant === "icon-only";

  const links = iconOnly
    ? [
        { key: "chat", label: "Chats", to: "/chat", icon: ICONS.chat },
        { key: "feed", label: "Feed", to: "/feed", icon: ICONS.feed },
        { key: "friends", label: "Friends", to: "/friends", icon: ICONS.friends },
        { key: "notifications", label: "Notifications", to: "/notifications", icon: ICONS.notifications },
        { key: "profile", label: "Profile", to: profileIdentifier ? `/profile/${profileIdentifier}` : "/feed", icon: ICONS.profile },
      ]
    : [
        { key: "feed", label: "Feed", to: "/feed", icon: ICONS.feed },
        { key: "search", label: "Search", to: "/search", icon: ICONS.search },
        { key: "notifications", label: "Notifications", to: "/notifications", icon: ICONS.notifications },
        { key: "chat", label: "Chats", to: "/chat", icon: ICONS.chat },
        { key: "profile", label: "Profile", to: profileIdentifier ? `/profile/${profileIdentifier}` : "/feed", icon: ICONS.profile },
      ];

  return (
    <div className={`social-nav ${iconOnly ? "icon-only" : ""} ${className}`.trim()}>
      {links.map((item) => {
        const isActive =
          item.key === "feed"
            ? location.pathname.startsWith("/feed")
            : item.key === "search"
              ? location.pathname.startsWith("/search")
            : item.key === "notifications"
              ? location.pathname.startsWith("/notifications")
            : item.key === "chat"
              ? location.pathname.startsWith("/chat")
            : item.key === "friends"
              ? location.pathname.startsWith("/friends")
              : location.pathname.startsWith("/profile/");
        return (
          <button
            key={item.key}
            type="button"
            className={`social-nav-btn ${isActive ? "active" : ""}`}
            onClick={() => nav(item.to)}
            aria-label={item.label}
            title={item.label}
          >
            {iconOnly ? <span className="social-nav-icon">{item.icon}</span> : <span>{item.label}</span>}
            {item.key === "notifications" && unreadCount > 0 && (
              <span className="social-nav-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

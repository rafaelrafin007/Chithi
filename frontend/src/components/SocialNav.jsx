import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import useNotificationCount from "../hooks/useNotificationCount";

export default function SocialNav({ className = "" }) {
  const nav = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { unreadCount } = useNotificationCount(!!user?.id);

  const profileIdentifier = user?.username || user?.id;

  const links = [
    { key: "feed", label: "Feed", to: "/feed" },
    { key: "notifications", label: "Notifications", to: "/notifications" },
    { key: "chat", label: "Chats", to: "/chat" },
    { key: "profile", label: "Profile", to: profileIdentifier ? `/profile/${profileIdentifier}` : "/feed" },
  ];

  return (
    <div className={`social-nav ${className}`.trim()}>
      {links.map((item) => {
        const isActive =
          item.key === "feed"
            ? location.pathname.startsWith("/feed")
            : item.key === "notifications"
              ? location.pathname.startsWith("/notifications")
            : item.key === "chat"
              ? location.pathname.startsWith("/chat")
              : location.pathname.startsWith("/profile/");
        return (
          <button
            key={item.key}
            type="button"
            className={`social-nav-btn ${isActive ? "active" : ""}`}
            onClick={() => nav(item.to)}
          >
            <span>{item.label}</span>
            {item.key === "notifications" && unreadCount > 0 && (
              <span className="social-nav-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

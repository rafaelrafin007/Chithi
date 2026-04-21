import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function SocialNav({ className = "" }) {
  const nav = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const profileIdentifier = user?.username || user?.id;

  const links = [
    { key: "feed", label: "Feed", to: "/feed" },
    { key: "chat", label: "Chats", to: "/chat" },
    { key: "profile", label: "Profile", to: profileIdentifier ? `/profile/${profileIdentifier}` : "/feed" },
  ];

  return (
    <div className={`social-nav ${className}`.trim()}>
      {links.map((item) => {
        const isActive =
          item.key === "feed"
            ? location.pathname.startsWith("/feed")
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
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

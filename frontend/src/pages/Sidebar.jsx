// src/pages/Sidebar.jsx
import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import ProfilePanel from "../pages/ProfilePanel";

export default function Sidebar({ users, selected, setSelected, theme, toggleTheme, width }) {
  const { user } = useAuth();
  const [showProfile, setShowProfile] = useState(false);

  const avatarUrl = user?.avatar_url || user?.profile?.avatar_url || null;
  const displayName = user?.display_name || user?.profile?.display_name || user?.username;

  // helper to get display name for any user object `u`
  const getDisplayName = (u) => u?.display_name || u?.profile?.display_name || u?.username || "Unknown";

  const getAvatar = (u) => u?.avatar_url || u?.profile?.avatar_url || null;

  const initials = (str) => (str ? str[0].toUpperCase() : "U");

  return (
    <div className="chat-sidebar" style={{ width }}>
      <div className="chat-sidebar-header" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Avatar button for current logged-in user */}
          <button
            className="avatar-btn"
            onClick={() => setShowProfile((s) => !s)}
            style={{
              border: "none",
              background: "transparent",
              padding: 0,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
            title="Open profile"
          >
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={displayName}
                style={{ width: 36, height: 36, borderRadius: "50%", objectFit: "cover" }}
              />
            ) : (
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  background: "#3498db",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                }}
              >
                {initials(displayName)}
              </div>
            )}
          </button>

          <div>
            <h2 style={{ margin: 0 }}>Chats</h2>
            <div style={{ fontSize: "0.85rem", opacity: 0.8 }}>{displayName}</div>
          </div>
        </div>

        <label className="switch" title="Toggle theme" style={{ marginLeft: "auto" }}>
          <input type="checkbox" checked={theme === "dark"} onChange={toggleTheme} />
          <span className="slider round"></span>
        </label>
      </div>

      {/* Profile panel (overlay) */}
      {showProfile && (
        <div className="profile-panel-backdrop" onClick={() => setShowProfile(false)}>
          <div className="profile-panel-overlay" onClick={(e) => e.stopPropagation()}>
            <ProfilePanel onClose={() => setShowProfile(false)} />
          </div>
        </div>
      )}

      {/* Users list */}
      {users.map((u) => {
        const name = getDisplayName(u);
        const avatar = getAvatar(u);
        const isActive = selected?.id === u.id;
        return (
          <div
            key={u.id}
            className={`chat-user ${isActive ? "active" : ""} ${u.unread > 0 ? "unread-highlight" : ""}`}
            onClick={() => setSelected(u)}
            style={{ display: "flex", gap: 10, alignItems: "center", padding: "10px 12px" }}
          >
            {/* Avatar */}
            <div style={{ minWidth: 44, minHeight: 44, display: "flex", alignItems: "center", justifyContent: "center" }}>
              {avatar ? (
                <img
                  src={avatar}
                  alt={name}
                  style={{ width: 44, height: 44, borderRadius: 8, objectFit: "cover" }}
                />
              ) : (
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 8,
                    background: "#7b61ff",
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                  }}
                >
                  {initials(name)}
                </div>
              )}
            </div>

            {/* Text area */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  className={u.unread > 0 ? "bold-username" : ""}
                  style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {name}
                </span>
                {u.unread > 0 && <span className="unread-badge">{u.unread}</span>}
              </div>

              {u.last_message?.content && (
                <small
                  className={`last-msg ${u.unread > 0 ? "bold-username" : ""}`}
                  style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {u.last_message.content.length > 40
                    ? u.last_message.content.slice(0, 40) + "..."
                    : u.last_message.content}
                </small>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

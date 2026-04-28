// src/pages/Sidebar.jsx
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import ProfilePanel from "../pages/ProfilePanel";

function formatListTime(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function Sidebar({
  users,
  selected,
  setSelected,
  theme,
  toggleTheme,
  width,
  showArchived = false,
  setShowArchived,
  onArchiveToggle,
  onMuteToggle,
  onDeleteConversation,
}) {
  const { user, logout } = useAuth();
  const [showProfile, setShowProfile] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [openRowMenuId, setOpenRowMenuId] = useState(null);
  const nav = useNavigate();
  const openRowMenuRef = useRef(null);

  const avatarUrl = user?.avatar_url || user?.profile?.avatar_url || null;
  const displayName = user?.display_name || user?.profile?.display_name || user?.username;

  // helper to get display name for any user object `u`
  const getDisplayName = (u) => u?.display_name || u?.profile?.display_name || u?.username || "Unknown";

  const getAvatar = (u) => u?.avatar_url || u?.profile?.avatar_url || null;

  const initials = (str) => (str ? str[0].toUpperCase() : "U");

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (!openRowMenuRef.current) return;
      if (openRowMenuRef.current.contains(event.target)) return;
      setOpenRowMenuId(null);
    };
    document.addEventListener("pointerdown", handleOutsideClick);
    return () => {
      document.removeEventListener("pointerdown", handleOutsideClick);
    };
  }, []);

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
      <div className="sidebar-users">
        {users.map((u) => {
          const name = getDisplayName(u);
          const avatar = getAvatar(u);
          const isActive = selected?.id === u.id;
          return (
            <div
              key={u.id}
              className={`chat-user ${isActive ? "active" : ""} ${u.unread > 0 && !u.is_muted ? "unread-highlight" : ""}`}
              onClick={() => {
                setSelected(u);
                setOpenRowMenuId(null);
              }}
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
                  {u.is_muted && <span className="friends-chip">Muted</span>}
                  {u.is_blocked_by_me && <span className="friends-chip blocked">Blocked</span>}
                  {u.has_blocked_me && <span className="friends-chip blocked">Blocked you</span>}
                  {u.unread > 0 && <span className="unread-badge">{u.unread}</span>}
                </div>

                {(u.last_message?.content || u.last_message?.attachment_url) && (
                  <small
                    className={`last-msg ${u.unread > 0 ? "bold-username" : ""}`}
                    style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {u.last_message.content
                      ? (u.last_message.content.length > 40
                        ? u.last_message.content.slice(0, 40) + "..."
                        : u.last_message.content)
                      : "Sent an attachment"}
                  </small>
                )}
                {u.last_message?.timestamp && (
                  <small className="chat-row-time">{formatListTime(u.last_message.timestamp)}</small>
                )}
              </div>

              <div
                className={`chat-row-overflow ${openRowMenuId === u.id ? "open" : ""}`}
                onClick={(e) => e.stopPropagation()}
                ref={openRowMenuId === u.id ? openRowMenuRef : null}
              >
                <button
                  type="button"
                  className="chat-row-overflow-btn"
                  aria-label="Conversation actions"
                  title="Conversation actions"
                  aria-haspopup="menu"
                  aria-expanded={openRowMenuId === u.id}
                  onClick={() => setOpenRowMenuId((prev) => (prev === u.id ? null : u.id))}
                >
                  <span aria-hidden="true">•••</span>
                </button>

                {openRowMenuId === u.id && (
                  <div className="chat-row-menu" role="menu">
                    <button
                      type="button"
                      className="chat-row-menu-item"
                      role="menuitem"
                      onClick={() => {
                        onMuteToggle?.(u.id, !u.is_muted);
                        setOpenRowMenuId(null);
                      }}
                    >
                      {u.is_muted ? "Unmute" : "Mute"}
                    </button>
                    <button
                      type="button"
                      className="chat-row-menu-item"
                      role="menuitem"
                      onClick={() => {
                        onArchiveToggle?.(u.id, !u.is_archived);
                        setOpenRowMenuId(null);
                      }}
                    >
                      {u.is_archived ? "Unarchive" : "Archive"}
                    </button>
                    <button
                      type="button"
                      className="chat-row-menu-item danger"
                      role="menuitem"
                      onClick={async () => {
                        const confirmed = window.confirm("Delete this chat for you? This will hide it from your chat list.");
                        if (!confirmed) return;
                        await onDeleteConversation?.(u.id);
                        setOpenRowMenuId(null);
                      }}
                    >
                      Delete chat
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom settings area */}
      <div className="sidebar-bottom">
        <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%", alignItems: "center" }}>
          {showArchived && (
            <button
              className="btn btn-secondary"
              onClick={() => setShowArchived?.(false)}
            >
              Back to Inbox
            </button>
          )}
          <button
            className="btn btn-secondary"
            onClick={() => setShowSettings((s) => !s)}
          >
            Settings
          </button>
        </div>
      </div>

      {showSettings && (
        <div className="sidebar-settings-backdrop" onClick={() => setShowSettings(false)}>
          <div className="sidebar-settings-panel" onClick={(e) => e.stopPropagation()}>
            <div className="sidebar-settings-row">
              <span>Theme</span>
              <label className="switch" title="Toggle theme">
                <input type="checkbox" checked={theme === "dark"} onChange={toggleTheme} />
                <span className="slider round"></span>
              </label>
            </div>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setShowArchived?.(!showArchived);
                setShowSettings(false);
              }}
            >
              {showArchived ? "Back to Inbox" : "View Archived"}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => {
                logout();
                nav("/login", { replace: true });
              }}
            >
              Logout
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

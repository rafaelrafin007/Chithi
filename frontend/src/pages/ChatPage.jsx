// src/pages/chatpage.jsx
import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import Sidebar from "./Sidebar";
import MessageBubble from "./MessageBubble";
import useChat from "../hooks/useChat";
import SocialNav from "../components/SocialNav";

export default function ChatPage() {
  const { user } = useAuth();
  const chat = useChat(user);
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const isResizingRef = useRef(false);

  const fileLabel = (file, url) => {
    if (!file && !url) return "attachment";
    const name = file?.name || (url ? url.split("/").pop() : "");
    return name || "attachment";
  };

  const fileExt = (file, url) => {
    const name = file?.name || (url ? url.split("/").pop() : "");
    return (name.split(".").pop() || "").toLowerCase();
  };

  const getDisplayName = (u) => u?.display_name || u?.profile?.display_name || u?.username || "Unknown";
  const getAvatar = (u) => u?.avatar_url || u?.profile?.avatar_url || null;
  const initials = (s) => (s ? s[0].toUpperCase() : "U");

  const selected = chat.selected;
  const isMessagingBlocked = !!selected && selected.can_message === false;
  const blockedReason = selected?.is_blocked_by_me
    ? "You blocked this user. Unblock from profile or friends page to send messages."
    : selected?.has_blocked_me
      ? "This user has blocked you. Messaging is unavailable."
      : "Messaging is unavailable for this conversation.";

  useEffect(() => {
    const handleMove = (e) => {
      if (!isResizingRef.current) return;
      const min = 220;
      const max = 420;
      const next = Math.max(min, Math.min(max, e.clientX));
      setSidebarWidth(next);
    };
    const handleUp = () => {
      isResizingRef.current = false;
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, []);

  return (
    <div className="chat-container">
      {/* Sidebar */}
      <Sidebar
        users={chat.users}
        selected={chat.selected}
        setSelected={chat.setSelected}
        theme={chat.theme}
        toggleTheme={chat.toggleTheme}
        width={sidebarWidth}
        showArchived={chat.showArchived}
        setShowArchived={chat.setShowArchived}
        onArchiveToggle={chat.setConversationArchived}
        onMuteToggle={chat.setConversationMuted}
      />

      <div
        className="sidebar-resizer"
        onMouseDown={() => {
          isResizingRef.current = true;
        }}
      />

      {/* Chat Window */}
      <div className="chat-window">
        <div className="chat-top-nav">
          <SocialNav className="chat-top-nav-strip" variant="icon-only" />
        </div>

        <div className="chat-header" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {selected ? (
            <>
              {/* avatar */}
              <div>
                {getAvatar(selected) ? (
                  <img
                    src={getAvatar(selected)}
                    alt={getDisplayName(selected)}
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
                    {initials(getDisplayName(selected))}
                  </div>
                )}
              </div>

              <div>
                <h3 style={{ margin: 0 }}>{getDisplayName(selected)}</h3>
                {selected && (
                  <small style={{ opacity: 0.7 }}>
                    {selected.is_online ? "Online" : "Offline"}
                    {selected.is_muted ? " | Muted" : ""}
                    {selected.is_archived ? " | Archived" : ""}
                  </small>
                )}
              </div>
              <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                <button
                  className="btn btn-secondary small"
                  onClick={() => chat.setConversationMuted(selected.id, !selected.is_muted)}
                >
                  {selected.is_muted ? "Unmute" : "Mute"}
                </button>
                <button
                  className="btn btn-secondary small"
                  onClick={() => chat.setConversationArchived(selected.id, !selected.is_archived)}
                >
                  {selected.is_archived ? "Unarchive" : "Archive"}
                </button>
              </div>
            </>
          ) : (
            <h3 style={{ margin: 0 }}>Select a user</h3>
          )}
        </div>

        {chat.conversationError && (
          <div className="chat-inline-error" style={{ padding: "8px 12px" }}>
            {chat.conversationError}
          </div>
        )}
        {chat.usersError && (
          <div className="chat-inline-error" style={{ padding: "8px 12px" }}>
            {chat.usersError}
          </div>
        )}
        {isMessagingBlocked && (
          <div className="chat-inline-error" style={{ padding: "8px 12px" }}>
            {blockedReason}
          </div>
        )}

        <div className="chat-messages">
          {!chat.selected && !chat.usersError && (
            <div className="chat-empty-state">Select a conversation to start chatting.</div>
          )}
          {chat.selected && chat.messages.length === 0 && !chat.conversationError && (
            <div className="chat-empty-state">No messages yet in this conversation.</div>
          )}
          {chat.messages.map((m) => {
            const mine = m.sender?.id === user?.id;
            return (
              <MessageBubble
                key={m.id}
                m={m}
                mine={mine}
                menuOpenFor={chat.menuOpenFor}
                setMenuOpenFor={chat.setMenuOpenFor}
                editingMessageId={chat.editingMessageId}
                editingText={chat.editingText}
                setEditingText={chat.setEditingText}
                startEdit={chat.startEdit}
                cancelEdit={chat.cancelEdit}
                submitEdit={chat.submitEdit}
                deleteMessage={chat.deleteMessage}
                formatTimestamp={chat.formatTimestamp}
                onReact={chat.sendReaction}
                currentUserId={user?.id}
              />
            );
          })}

          {chat.typing && chat.selected && (
            <div className="typing-indicator">
              {(chat.selected?.display_name || chat.selected?.profile?.display_name || chat.selected?.username)} is typing...
            </div>
          )}

          <div ref={chat.messagesEndRef} />
        </div>

        {/* Chat input + attach UI */}
        <div className="chat-input chat-input-column">
          {(chat.previewUrl || chat.selectedFile) && (
            <div className="attach-preview">
              {chat.selectedFile && chat.selectedFile.type?.startsWith("image/") ? (
                chat.previewUrl ? (
                  <img src={chat.previewUrl} alt={chat.selectedFile.name} className="preview-image" />
                ) : (
                  <div className="file-info">
                    <span>Image</span>
                    <span className="file-name">{chat.selectedFile?.name}</span>
                  </div>
                )
              ) : chat.previewUrl ? (
                <a href={chat.previewUrl} target="_blank" rel="noreferrer">
                  <img src={chat.previewUrl} alt={fileLabel(chat.selectedFile, chat.previewUrl)} className="preview-image" />
                </a>
              ) : (
                <div className="file-card">
                  <div className="file-card-icon">
                    {fileExt(chat.selectedFile, chat.previewUrl) === "pdf"
                      ? "PDF"
                      : (fileExt(chat.selectedFile, chat.previewUrl) || "FILE").toUpperCase()}
                  </div>
                  <div className="file-card-text">
                    <span className="file-card-name">{fileLabel(chat.selectedFile, chat.previewUrl)}</span>
                    <small>Attached file</small>
                  </div>
                </div>
              )}

              <div className="remove-btn-wrap">
                <button type="button" onClick={chat.removeAttachment} className="remove-btn" title="Remove attachment">
                  x
                </button>
              </div>
            </div>
          )}

          <div className="chat-input-row">
            <input type="file" id="chat-attach-input" className="hidden-input" onChange={chat.handleFileChange} />

            <button
              type="button"
              onClick={() => document.getElementById("chat-attach-input")?.click()}
              title="Attach a file"
              className="attach-btn"
              disabled={!selected || isMessagingBlocked}
            >
              +
            </button>

            <input
              placeholder={
                !selected
                  ? "Select a user to start chatting..."
                  : isMessagingBlocked
                    ? "Messaging unavailable due to block status"
                    : "Type a message..."
              }
              value={chat.text}
              onChange={chat.handleTyping}
              onKeyDown={(e) => e.key === "Enter" && chat.send()}
              className="message-input"
              disabled={!selected || isMessagingBlocked}
            />
            <button onClick={chat.send} disabled={!selected || isMessagingBlocked}>
              Send
            </button>
          </div>
          {chat.sendError && <div className="chat-inline-error">{chat.sendError}</div>}
        </div>
      </div>
    </div>
  );
}

// src/pages/chatpage.jsx
import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import Sidebar from "./Sidebar";
import MessageBubble from "./MessageBubble";
import useChat from "../hooks/useChat";

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
      />

      <div
        className="sidebar-resizer"
        onMouseDown={() => {
          isResizingRef.current = true;
        }}
      />

      {/* Chat Window */}
      <div className="chat-window">
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
                {selected?.last_message?.sender && (
                  <small style={{ opacity: 0.7 }}>
                    {selected.last_message.sender?.id === user?.id
                      ? "You"
                      : selected.last_message.sender?.display_name || selected.last_message.sender?.username}
                  </small>
                )}
              </div>
            </>
          ) : (
            <h3 style={{ margin: 0 }}>Select a user</h3>
          )}
        </div>

        <div className="chat-messages">
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
            >
              +
            </button>

            <input
              placeholder="Type a message..."
              value={chat.text}
              onChange={chat.handleTyping}
              onKeyDown={(e) => e.key === "Enter" && chat.send()}
              className="message-input"
            />
            <button onClick={chat.send}>Send</button>
          </div>
        </div>
      </div>
    </div>
  );
}

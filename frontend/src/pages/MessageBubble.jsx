// src/components/MessageBubble.jsx
import React from "react";

/**
 * Props:
 * - m: message object
 * - mine: boolean
 * - menuOpenFor, setMenuOpenFor
 * - editingMessageId, editingText, setEditingText
 * - startEdit, cancelEdit, submitEdit, deleteMessage
 * - formatTimestamp
 */
export default function MessageBubble({
  m,
  mine,
  menuOpenFor,
  setMenuOpenFor,
  editingMessageId,
  editingText,
  setEditingText,
  startEdit,
  cancelEdit,
  submitEdit,
  deleteMessage,
  formatTimestamp,
}) {
  const isEditingThis = editingMessageId === m.id;

  // Determine attachment presence (fields may vary depending on serializer)
  const attachmentUrl = m.attachment_url || m.attachment || null;
  const thumbUrl = m.attachment_thumb || m.attachment_thumb_url || null;
  const attachmentName = m.attachment_name || (attachmentUrl ? attachmentUrl.split("/").pop() : null);
  // try to infer extension from name/url
  const ext = (attachmentName || attachmentUrl || "").split(".").pop()?.toLowerCase() || "";

  // If message is deleted, do not render attachment
  const showAttachment = !!attachmentUrl && !m.is_deleted;

  const renderFileCard = () => (
    <div className="file-card" style={{
      display: "flex",
      gap: 10,
      alignItems: "center",
      padding: "8px 10px",
      borderRadius: 8,
      border: "1px solid rgba(255,255,255,0.04)",
      maxWidth: 320,
      background: "rgba(0,0,0,0.03)"
    }}>
      <div className="file-icon" style={{
        minWidth: 44,
        minHeight: 44,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 6,
        background: "rgba(255,255,255,0.02)",
        fontWeight: 700
      }}>
        {ext === "pdf" ? "PDF" : ext ? ext.toUpperCase() : "FILE"}
      </div>
      <div className="file-meta" style={{ overflow: "hidden" }}>
        <a href={attachmentUrl} target="_blank" rel="noreferrer" style={{
          display: "block",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}>{attachmentName || "download"}</a>
        {/* you could show size if serializer provides it */}
      </div>
    </div>
  );

  return (
    <div className={`message-row ${mine ? "mine" : "other"}`}>
      <div className={`message ${mine ? "sent" : "received"}`}>
        {isEditingThis ? (
          <div className="edit-form">
            <input
              className="edit-input"
              value={editingText}
              onChange={(e) => setEditingText(e.target.value)}
              placeholder="Edit message..."
            />
            <div className="edit-actions">
              <button className="btn btn-primary" onClick={submitEdit}>Save</button>
              <button className="btn btn-secondary" onClick={cancelEdit}>Cancel</button>
            </div>
          </div>
        ) : (
          <>
            {/* Message content */}
            <p className="message-content">
              {m.content}
              {m.is_edited && !m.is_deleted && (
                <em className="edited-tag">(edited)</em>
              )}
            </p>

            {/* Attachment preview (image or file link/card) */}
            {showAttachment && (
              <div className="message-attachment" style={{ marginTop: 8 }}>
                {/* If we have a thumb (server-generated or client data-url), show it */}
                {thumbUrl ? (
                  <a href={attachmentUrl} target="_blank" rel="noreferrer">
                    <img
                      src={thumbUrl}
                      alt={attachmentName || "attachment"}
                      style={{ maxWidth: 280, borderRadius: 8, display: "block" }}
                    />
                  </a>
                ) : (
                  // No thumb: if extension looks like an image, show the image itself
                  (attachmentUrl && attachmentUrl.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i)) ? (
                    <a href={attachmentUrl} target="_blank" rel="noreferrer">
                      <img
                        src={attachmentUrl}
                        alt="attachment"
                        style={{ maxWidth: 280, borderRadius: 8, display: "block" }}
                      />
                    </a>
                  ) : (
                    // Generic file card (PDF or other)
                    renderFileCard()
                  )
                )}
              </div>
            )}

            <span className="chat-timestamp">
              {formatTimestamp(m.timestamp)}
              {mine && (
                <span className="read-receipt">
                  {m.read ? "✓✓" : m.delivered ? "✓✓" : "✓"}
                </span>
              )}
            </span>

            {mine && !m.is_deleted && (
              <button
                className="message-menu-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpenFor(menuOpenFor === m.id ? null : m.id);
                }}
                aria-label="options"
                title="Message options"
              >
                ⌄
              </button>
            )}
          </>
        )}
      </div>

      {menuOpenFor === m.id && (
        <div className={`message-menu ${mine ? "align-end" : "align-start"}`}>
          <button className="menu-item" onClick={() => startEdit(m)}>✏️ Edit</button>
          <button className="menu-item delete" onClick={() => deleteMessage(m.id)}>🗑️ Delete</button>
        </div>
      )}
    </div>
  );
}

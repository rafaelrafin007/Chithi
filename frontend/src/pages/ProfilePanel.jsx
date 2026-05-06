// src/pages/ProfilePanel.jsx
import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";

/**
 * ProfilePanel
 * - per-field inline editors for display_name, about, phone, avatar
 * - uses updateProfile(payload, avatarFile) from AuthContext
 *
 * UX:
 * - shows field value + small edit icon
 * - when editing, shows input/textarea + Save / Cancel for that field only
 */
export default function ProfilePanel({ onClose }) {
  const { user, updateProfile } = useAuth();
  const profile = user?.profile || {};

  // local copies
  const [displayName, setDisplayName] = useState(profile.display_name || "");
  const [about, setAbout] = useState(profile.about || "");
  const [phone, setPhone] = useState(profile.phone || "");
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(profile.avatar_url || null);

  // editing state: null | 'name' | 'about' | 'phone' | 'avatar'
  const [editing, setEditing] = useState(null);

  // per-field loading / error
  const [loadingField, setLoadingField] = useState(null);
  const [errorField, setErrorField] = useState(null);

  // keep local state in sync with user from context
  useEffect(() => {
    setDisplayName(profile.display_name || "");
    setAbout(profile.about || "");
    setPhone(profile.phone || "");
    setAvatarPreview(profile.avatar_url || null);
    // clear avatarFile when profile changes from server
    setAvatarFile(null);
  }, [user, profile.about, profile.display_name, profile.phone, profile.avatar_url]);

  // Avatar handlers
  const handleAvatarChange = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    // revoke previous object url if any
    if (avatarPreview && avatarPreview.startsWith("blob:")) {
      try {
        URL.revokeObjectURL(avatarPreview);
      } catch {}
    }
    setAvatarFile(f);
    setAvatarPreview(URL.createObjectURL(f));
    setEditing("avatar");
    e.target.value = "";
  };

  const cancelAvatarSelection = () => {
    if (avatarPreview && avatarPreview.startsWith("blob:")) {
      try {
        URL.revokeObjectURL(avatarPreview);
      } catch {}
    }
    setAvatarFile(null);
    setAvatarPreview(profile.avatar_url || null);
    setEditing(null);
    setErrorField(null);
  };

  // Generic save function for field (name|about|phone)
  const saveField = async (field) => {
    setErrorField(null);
    setLoadingField(field);
    try {
      if (field === "avatar") {
        // avatarFile present
        if (!avatarFile) throw new Error("No avatar selected");
        await updateProfile({}, avatarFile);
      } else {
        const payload = {};
        if (field === "name") payload.display_name = displayName;
        if (field === "about") payload.about = about;
        if (field === "phone") payload.phone = phone;
        await updateProfile(payload, null);
      }
      // success
      setEditing(null);
      setLoadingField(null);
      setErrorField(null);
    } catch (err) {
      // err may be object; try to display a friendly message
      console.error("Profile update error:", err);
      let msg = "Failed to update";
      if (typeof err === "string") msg = err;
      else if (err?.response?.data) msg = JSON.stringify(err.response.data);
      else if (err?.message) msg = err.message;
      setErrorField(msg);
      setLoadingField(null);
    }
  };

  const cancelEdit = (field) => {
    // revert local changes to server state
    setErrorField(null);
    if (field === "name") setDisplayName(profile.display_name || "");
    if (field === "about") setAbout(profile.about || "");
    if (field === "phone") setPhone(profile.phone || "");
    if (field === "avatar") {
      cancelAvatarSelection();
    } else {
      setEditing(null);
    }
  };

  return (
    <div className="profile-panel">
      <div className="profile-header">
        <div className="avatar-block">
          {avatarPreview ? (
            <img src={avatarPreview} alt="avatar" className="avatar-img" />
          ) : (
            <div className="avatar-placeholder">
              {(displayName || user?.display_name || user?.username || "U")[0]?.toUpperCase()}
            </div>
          )}

          <input
            id="profile-avatar-input"
            type="file"
            accept="image/*"
            className="hidden-input"
            onChange={handleAvatarChange}
          />

          <div className="avatar-actions">
            {/* always allow picking a new file (opens file dialog) */}
            <button
              type="button"
              className="btn btn-secondary small"
              onClick={() => document.getElementById("profile-avatar-input")?.click()}
              title="Change avatar"
            >
              Change
            </button>

            {/* if user selected a new avatar but not yet saved, show Cancel */}
            {editing === "avatar" && avatarFile && (
              <button
                type="button"
                className="btn small"
                onClick={() => cancelEdit("avatar")}
                title="Cancel avatar change"
              >
                Cancel
              </button>
            )}
          </div>
        </div>

        <div className="profile-meta">
          {/* show display name if set (local state), else fallback to normalized user fields */}
          <div className="meta-username">{displayName || user?.display_name || user?.username}</div>
          <div className="meta-email">{user?.email}</div>
        </div>
      </div>

      {/* Display name field */}
      <div className="profile-field">
        <label className="field-label">Display name</label>
        {editing === "name" ? (
          <div className="editor-row">
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="editor-input"
              placeholder="Your name"
            />
            <div className="editor-actions">
              <button className="btn btn-primary" onClick={() => saveField("name")} disabled={loadingField === "name"}>
                {loadingField === "name" ? "Saving..." : "Save"}
              </button>
              <button className="btn btn-secondary" onClick={() => cancelEdit("name")}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="field-value-row">
            <div className="field-value">{displayName || <span className="field-empty">No name set</span>}</div>
            <button className="icon-btn edit-icon" onClick={() => setEditing("name")} title="Edit name">
              Edit
            </button>
          </div>
        )}
        {errorField && editing === "name" && <div className="error-text">{errorField}</div>}
      </div>

      {/* About field */}
      <div className="profile-field">
        <label className="field-label">About</label>
        {editing === "about" ? (
          <div className="editor-row">
            <textarea
              value={about}
              onChange={(e) => setAbout(e.target.value)}
              rows={3}
              className="editor-textarea"
            />
            <div className="editor-actions">
              <button
                className="btn btn-primary"
                onClick={() => saveField("about")}
                disabled={loadingField === "about"}
              >
                {loadingField === "about" ? "Saving..." : "Save"}
              </button>
              <button className="btn btn-secondary" onClick={() => cancelEdit("about")}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="field-value-row">
            <div className="field-value">{about || <span className="field-empty">No about set</span>}</div>
            <button className="icon-btn edit-icon" onClick={() => setEditing("about")} title="Edit about">
              Edit
            </button>
          </div>
        )}
        {errorField && editing === "about" && <div className="error-text">{errorField}</div>}
      </div>

      {/* Phone field */}
      <div className="profile-field">
        <label className="field-label">Phone</label>
        {editing === "phone" ? (
          <div className="editor-row">
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="editor-input"
              placeholder="Phone number"
            />
            <div className="editor-actions">
              <button
                className="btn btn-primary"
                onClick={() => saveField("phone")}
                disabled={loadingField === "phone"}
              >
                {loadingField === "phone" ? "Saving..." : "Save"}
              </button>
              <button className="btn btn-secondary" onClick={() => cancelEdit("phone")}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="field-value-row">
            <div className="field-value">{phone || <span className="field-empty">No phone set</span>}</div>
            <button className="icon-btn edit-icon" onClick={() => setEditing("phone")} title="Edit phone">
              Edit
            </button>
          </div>
        )}
        {errorField && editing === "phone" && <div className="error-text">{errorField}</div>}
      </div>

      {/* Avatar save action (shown only when avatarFile selected and editing avatar) */}
      {editing === "avatar" && avatarFile && (
        <div className="profile-field avatar-save-row">
          <div className="avatar-save-actions">
            <button
              className="btn btn-primary"
              onClick={() => saveField("avatar")}
              disabled={loadingField === "avatar"}
            >
              {loadingField === "avatar" ? "Saving..." : "Save avatar"}
            </button>
            <button className="btn btn-secondary" onClick={() => cancelEdit("avatar")}>
              Cancel
            </button>
          </div>
          {errorField && <div className="error-text">{errorField}</div>}
        </div>
      )}

      {/* close button at bottom (optional) */}
      <div className="profile-close-row">
        {onClose && (
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        )}
      </div>
    </div>
  );
}

import React, { useEffect, useMemo, useState } from "react";
import { createPost } from "../services/api";

function parseError(err) {
  const data = err?.response?.data;
  if (!data) return err?.message || "Could not publish the post.";
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  if (Array.isArray(data)) return data.join(" ");
  const firstKey = Object.keys(data)[0];
  if (!firstKey) return "Could not publish the post.";
  const value = data[firstKey];
  if (Array.isArray(value)) return value.join(" ");
  return String(value);
}

export default function CreatePostComposer({ onCreated }) {
  const [content, setContent] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [image, setImage] = useState(null);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState("");

  const previewUrl = useMemo(() => (image ? URL.createObjectURL(image) : null), [image]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const resetComposer = () => {
    setContent("");
    setVisibility("public");
    setImage(null);
  };

  const onSubmit = async () => {
    if (posting) return;
    setError("");
    if (!content.trim() && !image) {
      setError("Write something or attach an image.");
      return;
    }

    setPosting(true);
    try {
      const { data } = await createPost({
        content: content.trim(),
        visibility,
        image,
      });
      resetComposer();
      onCreated?.(data);
    } catch (err) {
      setError(parseError(err));
    } finally {
      setPosting(false);
    }
  };

  return (
    <section className="social-card composer-card">
      <h3 className="social-card-title">Create Post</h3>
      <textarea
        className="social-textarea"
        rows={4}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Share what is on your mind..."
      />

      <div className="composer-controls">
        <select
          className="social-select"
          value={visibility}
          onChange={(e) => setVisibility(e.target.value)}
          disabled={posting}
        >
          <option value="public">Public</option>
          <option value="followers_only">Followers only</option>
          <option value="private">Private</option>
        </select>

        <label className="social-upload-btn">
          Attach Image
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setImage(e.target.files?.[0] || null)}
            disabled={posting}
            className="hidden-input"
          />
        </label>
      </div>

      {previewUrl && (
        <div className="composer-preview">
          <img src={previewUrl} alt="post preview" />
          <button type="button" className="social-link-btn" onClick={() => setImage(null)} disabled={posting}>
            Remove
          </button>
        </div>
      )}

      {error && <div className="social-error">{error}</div>}

      <div className="composer-submit-row">
        <button type="button" className="social-action-btn" onClick={onSubmit} disabled={posting}>
          {posting ? "Posting..." : "Post"}
        </button>
      </div>
    </section>
  );
}

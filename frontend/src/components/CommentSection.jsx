import React, { useCallback, useEffect, useState } from "react";
import { createComment, deleteComment, editComment, getComments } from "../services/api";
import { SOCIAL_REALTIME_EVENT_NAME } from "../hooks/useSocialRealtime";

function normalizePaged(payload) {
  if (Array.isArray(payload)) {
    return { results: payload, next: null, count: payload.length };
  }
  if (payload && Array.isArray(payload.results)) {
    return {
      results: payload.results,
      next: payload.next || null,
      count: typeof payload.count === "number" ? payload.count : payload.results.length,
    };
  }
  return { results: [], next: null, count: 0 };
}

function parseError(err, fallback) {
  const data = err?.response?.data;
  if (!data) return fallback;
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  const key = Object.keys(data)[0];
  const val = key ? data[key] : null;
  if (Array.isArray(val)) return val.join(" ");
  return String(val || fallback);
}

function displayName(user) {
  return user?.display_name || user?.username || "Unknown";
}

function formatTime(ts) {
  if (!ts) return "";
  const date = new Date(ts);
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function CommentSection({ postId, currentUserId, initialCount = 0, onCountChange }) {
  const [comments, setComments] = useState([]);
  const [nextPage, setNextPage] = useState(null);
  const [, setCount] = useState(initialCount || 0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editingText, setEditingText] = useState("");

  const applyCount = useCallback((nextCount) => {
    setCount(nextCount);
    onCountChange?.(nextCount);
  }, [onCountChange]);

  const bumpCount = useCallback((delta) => {
    setCount((prev) => {
      const next = Math.max(0, prev + delta);
      onCountChange?.(next);
      return next;
    });
  }, [onCountChange]);

  useEffect(() => {
    setCount(initialCount || 0);
  }, [initialCount]);

  useEffect(() => {
    const handler = (event) => {
      const payload = event?.detail;
      if (!payload || payload.post_id !== postId) return;

      if (payload.event === "comment_created" && payload.comment) {
        setComments((prev) => {
          const exists = prev.some((item) => item.id === payload.comment.id);
          if (exists) {
            return prev.map((item) => (item.id === payload.comment.id ? payload.comment : item));
          }
          return [...prev, payload.comment];
        });
        if (typeof payload.comment_count === "number") {
          applyCount(payload.comment_count);
        }
        return;
      }

      if (payload.event === "comment_updated" && payload.comment) {
        setComments((prev) =>
          prev.map((item) => (item.id === payload.comment.id ? payload.comment : item))
        );
        if (typeof payload.comment_count === "number") {
          applyCount(payload.comment_count);
        }
        return;
      }

      if (payload.event === "comment_deleted" && (payload.comment || payload.comment_id)) {
        const targetId = payload.comment?.id || payload.comment_id;
        setComments((prev) =>
          prev.map((item) =>
            item.id === targetId
              ? {
                  ...item,
                  ...(payload.comment || {}),
                  is_deleted: true,
                  content: payload.comment?.content || "This comment was deleted",
                }
              : item
          )
        );
        if (typeof payload.comment_count === "number") {
          applyCount(payload.comment_count);
        }
      }
    };

    window.addEventListener(SOCIAL_REALTIME_EVENT_NAME, handler);
    return () => window.removeEventListener(SOCIAL_REALTIME_EVENT_NAME, handler);
  }, [applyCount, postId]);

  const loadComments = async ({ page = 1, append = false } = {}) => {
    setError("");
    if (!append) setLoading(true);
    else setLoadingMore(true);
    try {
      const { data } = await getComments(postId, { page });
      const normalized = normalizePaged(data);
      setComments((prev) => (append ? [...prev, ...normalized.results] : normalized.results));
      setNextPage(normalized.next);
    } catch (err) {
      setError(parseError(err, "Failed to load comments."));
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    loadComments({ page: 1, append: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId]);

  const submitComment = async () => {
    if (submitting) return;
    const content = draft.trim();
    if (!content) return;
    setSubmitting(true);
    setError("");
    try {
      const { data } = await createComment(postId, { content, parent_comment: null });
      setComments((prev) => (prev.some((item) => item.id === data.id) ? prev : [...prev, data]));
      setDraft("");
      bumpCount(1);
    } catch (err) {
      setError(parseError(err, "Failed to add comment."));
    } finally {
      setSubmitting(false);
    }
  };

  const saveEdit = async (commentId) => {
    const content = editingText.trim();
    if (!content) return;
    try {
      const { data } = await editComment(commentId, { content });
      setComments((prev) => prev.map((item) => (item.id === commentId ? data : item)));
      setEditingId(null);
      setEditingText("");
    } catch (err) {
      setError(parseError(err, "Failed to edit comment."));
    }
  };

  const removeComment = async (commentId) => {
    try {
      const existing = comments.find((item) => item.id === commentId);
      await deleteComment(commentId);
      setComments((prev) =>
        prev.map((item) =>
          item.id === commentId
            ? { ...item, is_deleted: true, content: "This comment was deleted" }
            : item
        )
      );
      if (existing && !existing.is_deleted) bumpCount(-1);
    } catch (err) {
      setError(parseError(err, "Failed to delete comment."));
    }
  };

  const loadMore = async () => {
    if (!nextPage || loadingMore) return;
    try {
      const url = new URL(nextPage);
      const page = Number(url.searchParams.get("page") || "1");
      await loadComments({ page, append: true });
    } catch {
      await loadComments({ page: 1, append: true });
    }
  };

  if (loading) {
    return <div className="comment-state">Loading comments...</div>;
  }

  return (
    <div className="comment-section">
      <div className="comment-composer">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Write a comment..."
          className="comment-input"
          onKeyDown={(e) => e.key === "Enter" && submitComment()}
        />
        <button type="button" className="social-link-btn" disabled={submitting} onClick={submitComment}>
          {submitting ? "Posting..." : "Post"}
        </button>
      </div>

      {error && <div className="social-inline-error">{error}</div>}

      {comments.length === 0 ? (
        <div className="comment-state">No comments yet.</div>
      ) : (
        <div className="comment-list">
          {comments.map((comment) => {
            const mine = comment.author?.id === currentUserId;
            const isDeleted = !!comment.is_deleted;
            return (
              <div className={`comment-item ${isDeleted ? "deleted" : ""}`} key={comment.id}>
                <div className="comment-meta">
                  <span className="comment-author">{displayName(comment.author)}</span>
                  {comment.parent_comment && (
                    <span className="comment-parent">reply to #{comment.parent_comment}</span>
                  )}
                  <span className="comment-time">{formatTime(comment.created_at)}</span>
                </div>

                {editingId === comment.id ? (
                  <div className="comment-edit-row">
                    <input
                      type="text"
                      value={editingText}
                      onChange={(e) => setEditingText(e.target.value)}
                      className="comment-input"
                    />
                    <button type="button" className="social-link-btn" onClick={() => saveEdit(comment.id)}>
                      Save
                    </button>
                    <button
                      type="button"
                      className="social-link-btn"
                      onClick={() => {
                        setEditingId(null);
                        setEditingText("");
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="comment-content">{comment.content || "No content"}</div>
                )}

                {mine && !isDeleted && editingId !== comment.id && (
                  <div className="comment-actions">
                    <button
                      type="button"
                      className="social-link-btn"
                      onClick={() => {
                        setEditingId(comment.id);
                        setEditingText(comment.content || "");
                      }}
                    >
                      Edit
                    </button>
                    <button type="button" className="social-link-btn danger" onClick={() => removeComment(comment.id)}>
                      Delete
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {nextPage && (
        <button type="button" className="social-load-btn" onClick={loadMore} disabled={loadingMore}>
          {loadingMore ? "Loading..." : "Load more comments"}
        </button>
      )}
    </div>
  );
}

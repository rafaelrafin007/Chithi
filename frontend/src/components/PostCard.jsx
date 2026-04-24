import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { deletePost, editPost, likePost, reportPost, unlikePost } from "../services/api";
import CommentSection from "./CommentSection";

function formatPostTime(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function authorName(author) {
  return author?.display_name || author?.username || "Unknown";
}

export default function PostCard({
  post,
  currentUserId,
  onPostUpdated,
  onPostRemoved,
  initialCommentsOpen = false,
  showOpenPostButton = true,
}) {
  const nav = useNavigate();
  const [showComments, setShowComments] = useState(initialCommentsOpen);
  const [isLiking, setIsLiking] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(post?.content || "");
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isReporting, setIsReporting] = useState(false);
  const [reportMessage, setReportMessage] = useState("");
  const [error, setError] = useState("");

  const mine = post?.author?.id === currentUserId;

  useEffect(() => {
    setShowComments(initialCommentsOpen);
  }, [initialCommentsOpen, post?.id]);

  const setCountFromComments = (nextCount) => {
    onPostUpdated?.(post.id, { comment_count: nextCount });
  };

  const handleLikeToggle = async () => {
    if (isLiking) return;
    const wasLiked = !!post.is_liked_by_me;
    const optimistic = {
      is_liked_by_me: !wasLiked,
      like_count: Math.max(0, (post.like_count || 0) + (wasLiked ? -1 : 1)),
    };

    onPostUpdated?.(post.id, optimistic);
    setIsLiking(true);
    setError("");
    try {
      if (wasLiked) await unlikePost(post.id);
      else await likePost(post.id);
    } catch (err) {
      onPostUpdated?.(post.id, {
        is_liked_by_me: wasLiked,
        like_count: post.like_count || 0,
      });
      setError(err?.response?.data?.detail || "Could not update like.");
    } finally {
      setIsLiking(false);
    }
  };

  const handleSaveEdit = async () => {
    const content = editText.trim();
    if (!content && (!post.media || post.media.length === 0)) {
      setError("Post cannot be empty.");
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      const { data } = await editPost(post.id, { content });
      onPostUpdated?.(post.id, data);
      setIsEditing(false);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not update post.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    setError("");
    try {
      await deletePost(post.id);
      onPostRemoved?.(post.id);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not delete post.");
      setIsDeleting(false);
    }
  };

  const handleReport = async () => {
    if (mine || isReporting) return;
    const reason = window.prompt("Reason for report (e.g. spam, abuse)", "spam");
    if (!reason) return;
    const details = window.prompt("Additional details (optional)", "") || "";
    setIsReporting(true);
    setError("");
    setReportMessage("");
    try {
      await reportPost(post.id, { reason, details });
      setReportMessage("Post reported.");
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not report post.");
    } finally {
      setIsReporting(false);
    }
  };

  const authorIdentifier = post?.author?.username || post?.author?.id;

  return (
    <article className="social-card post-card">
      <div className="post-header">
        <button
          type="button"
          className="post-author-btn"
          onClick={() => authorIdentifier && nav(`/profile/${authorIdentifier}`)}
        >
          {post?.author?.avatar_url ? (
            <img src={post.author.avatar_url} alt={authorName(post.author)} className="post-avatar" />
          ) : (
            <div className="post-avatar fallback">{authorName(post.author).charAt(0).toUpperCase()}</div>
          )}
          <div className="post-author-text">
            <div className="post-author-name">{authorName(post.author)}</div>
            <div className="post-author-username">@{post?.author?.username || "unknown"}</div>
          </div>
        </button>
        <div className="post-time">{formatPostTime(post.created_at)}</div>
      </div>

      {isEditing ? (
        <div className="post-edit-box">
          <textarea
            rows={3}
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="social-textarea"
          />
          <div className="post-inline-actions">
            <button type="button" className="social-link-btn" onClick={handleSaveEdit} disabled={isSaving}>
              {isSaving ? "Saving..." : "Save"}
            </button>
            <button type="button" className="social-link-btn" onClick={() => setIsEditing(false)} disabled={isSaving}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        post?.content && <p className="post-content">{post.content}</p>
      )}

      {Array.isArray(post?.media) && post.media.length > 0 && (
        <div className="post-media-grid">
          {post.media.map((item) => (
            <img
              key={item.id}
              src={item.file_url}
              alt="post media"
              className="post-media-item"
            />
          ))}
        </div>
      )}

      <div className="post-stats">
        <span>{post.like_count || 0} likes</span>
        <span>{post.comment_count || 0} comments</span>
      </div>

      <div className="post-actions">
        <button type="button" className="social-link-btn" onClick={handleLikeToggle} disabled={isLiking}>
          {post.is_liked_by_me ? "Unlike" : "Like"}
        </button>
        <button type="button" className="social-link-btn" onClick={() => setShowComments((v) => !v)}>
          {showComments ? "Hide comments" : "Comment"}
        </button>
        {showOpenPostButton && (
          <button type="button" className="social-link-btn" onClick={() => nav(`/post/${post.id}`)}>
            Open post
          </button>
        )}
        {mine && !isEditing && (
          <>
            <button type="button" className="social-link-btn" onClick={() => setIsEditing(true)}>
              Edit
            </button>
            <button type="button" className="social-link-btn danger" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? "Deleting..." : "Delete"}
            </button>
          </>
        )}
        {!mine && (
          <button type="button" className="social-link-btn danger" onClick={handleReport} disabled={isReporting}>
            {isReporting ? "Reporting..." : "Report post"}
          </button>
        )}
      </div>

      {error && <div className="social-inline-error">{error}</div>}
      {reportMessage && <div className="social-inline-success">{reportMessage}</div>}

      {showComments && (
        <CommentSection
          postId={post.id}
          currentUserId={currentUserId}
          initialCount={post.comment_count || 0}
          onCountChange={setCountFromComments}
        />
      )}
    </article>
  );
}

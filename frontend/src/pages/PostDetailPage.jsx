import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getPostDetail } from "../services/api";
import { useAuth } from "../context/AuthContext";
import SocialNav from "../components/SocialNav";
import PostCard from "../components/PostCard";
import useSocialRealtime from "../hooks/useSocialRealtime";

export default function PostDetailPage() {
  const { postId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const numericPostId = Number(postId);

  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusCode, setStatusCode] = useState(null);
  const [deleted, setDeleted] = useState(false);

  useEffect(() => {
    const theme = localStorage.getItem("theme") || "dark";
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
  }, []);

  const loadPost = useCallback(async () => {
    if (!numericPostId) {
      setLoading(false);
      setStatusCode(404);
      setError("Invalid post id.");
      return;
    }

    setLoading(true);
    setDeleted(false);
    setError("");
    setStatusCode(null);

    try {
      const { data } = await getPostDetail(numericPostId);
      setPost(data);
    } catch (err) {
      const status = err?.response?.status || null;
      setStatusCode(status);
      if (status === 403) {
        setError("You do not have permission to view this post.");
      } else if (status === 404) {
        setError("Post not found or no longer available.");
      } else {
        setError(err?.response?.data?.detail || "Unable to load this post right now.");
      }
      setPost(null);
    } finally {
      setLoading(false);
    }
  }, [numericPostId]);

  useEffect(() => {
    loadPost();
  }, [loadPost]);

  const handlePostUpdated = (targetPostId, patch) => {
    if (targetPostId !== numericPostId) return;
    setPost((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const handlePostRemoved = (targetPostId) => {
    if (targetPostId !== numericPostId) return;
    setDeleted(true);
    setPost(null);
  };

  const handleRealtimeEvent = useCallback(
    (payload) => {
      const eventName = payload?.event;
      if (!eventName || payload?.post_id !== numericPostId) return;

      if (eventName === "post_updated") {
        setPost((prev) => (prev ? { ...prev, ...(payload.post || {}) } : prev));
        return;
      }

      if (eventName === "post_deleted") {
        setDeleted(true);
        setPost(null);
        return;
      }

      if (eventName === "post_liked" || eventName === "post_unliked") {
        setPost((prev) => {
          if (!prev) return prev;
          const next = { ...prev };
          if (typeof payload.like_count === "number") {
            next.like_count = payload.like_count;
          }
          if (payload.actor_id && payload.actor_id === user?.id) {
            next.is_liked_by_me = eventName === "post_liked";
          }
          return next;
        });
        return;
      }

      if (
        (eventName === "comment_created" || eventName === "comment_updated" || eventName === "comment_deleted") &&
        typeof payload.comment_count === "number"
      ) {
        setPost((prev) => (prev ? { ...prev, comment_count: payload.comment_count } : prev));
      }
    },
    [numericPostId, user?.id]
  );

  useSocialRealtime(handleRealtimeEvent, !!user?.id);

  return (
    <div className="social-page">
      <div className="social-shell with-side-nav">
        <aside className="social-side-panel">
          <SocialNav variant="sidebar" />
        </aside>
        <div className="social-main">
          <div className="social-top">
            <div>
              <div className="social-kicker">Chithi Social</div>
              <h2>Post</h2>
            </div>
          </div>

          {loading ? (
            <div className="social-state">Loading post...</div>
          ) : deleted ? (
            <div className="social-state">
              <p>This post was deleted.</p>
              <button type="button" className="social-action-btn" onClick={() => nav("/feed")}>
                Back to feed
              </button>
            </div>
          ) : post ? (
            <PostCard
              post={post}
              currentUserId={user?.id}
              onPostUpdated={handlePostUpdated}
              onPostRemoved={handlePostRemoved}
              initialCommentsOpen
              showOpenPostButton={false}
            />
          ) : (
            <div className="social-state error">
              <p>{error || "Post not available."}</p>
              <div className="post-detail-actions">
                {statusCode !== 404 && (
                  <button type="button" className="social-action-btn" onClick={loadPost}>
                    Retry
                  </button>
                )}
                <button type="button" className="social-action-btn secondary" onClick={() => nav("/feed")}>
                  Back to feed
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

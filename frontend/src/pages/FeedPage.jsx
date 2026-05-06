import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getFeed } from "../services/api";
import { useAuth } from "../context/AuthContext";
import SocialNav from "../components/SocialNav";
import CreatePostComposer from "../components/CreatePostComposer";
import PostCard from "../components/PostCard";
import useSocialRealtime from "../hooks/useSocialRealtime";

function normalizePaged(payload) {
  if (Array.isArray(payload)) {
    return { results: payload, next: null };
  }
  if (payload && Array.isArray(payload.results)) {
    return { results: payload.results, next: payload.next || null };
  }
  return { results: [], next: null };
}

export default function FeedPage() {
  const nav = useNavigate();
  const { user } = useAuth();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [nextPage, setNextPage] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const theme = localStorage.getItem("theme") || "dark";
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
  }, []);

  const loadFeed = useCallback(async ({ page = 1, append = false } = {}) => {
    if (!append) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const { data } = await getFeed({ page });
      const normalized = normalizePaged(data);
      setPosts((prev) => (append ? [...prev, ...normalized.results] : normalized.results));
      setNextPage(normalized.next);
    } catch (err) {
      setError(err?.response?.data?.detail || "Unable to load feed right now.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadFeed({ page: 1, append: false });
  }, [loadFeed]);

  const handlePostCreated = (post) => {
    setPosts((prev) => [post, ...prev]);
  };

  const handlePostUpdated = (postId, patch) => {
    setPosts((prev) =>
      prev.map((item) => (item.id === postId ? { ...item, ...patch } : item))
    );
  };

  const handlePostRemoved = (postId) => {
    setPosts((prev) => prev.filter((item) => item.id !== postId));
  };

  const handleRealtimeEvent = useCallback(
    (payload) => {
      const eventName = payload?.event;
      if (!eventName) return;

      if (eventName === "post_created" && payload.post) {
        setPosts((prev) => {
          const exists = prev.some((item) => item.id === payload.post.id);
          if (exists) {
            return prev.map((item) => (item.id === payload.post.id ? { ...item, ...payload.post } : item));
          }
          return [payload.post, ...prev];
        });
        return;
      }

      if (eventName === "post_updated" && payload.post_id) {
        setPosts((prev) =>
          prev.map((item) => (item.id === payload.post_id ? { ...item, ...(payload.post || {}) } : item))
        );
        return;
      }

      if (eventName === "post_deleted" && payload.post_id) {
        setPosts((prev) => prev.filter((item) => item.id !== payload.post_id));
        return;
      }

      if ((eventName === "post_liked" || eventName === "post_unliked") && payload.post_id) {
        setPosts((prev) =>
          prev.map((item) => {
            if (item.id !== payload.post_id) return item;
            const next = { ...item };
            if (typeof payload.like_count === "number") {
              next.like_count = payload.like_count;
            }
            if (payload.actor_id && payload.actor_id === user?.id) {
              next.is_liked_by_me = eventName === "post_liked";
            }
            return next;
          })
        );
        return;
      }

      if (
        (eventName === "comment_created" || eventName === "comment_updated" || eventName === "comment_deleted") &&
        payload.post_id &&
        typeof payload.comment_count === "number"
      ) {
        setPosts((prev) =>
          prev.map((item) =>
            item.id === payload.post_id ? { ...item, comment_count: payload.comment_count } : item
          )
        );
      }
    },
    [user?.id]
  );

  useSocialRealtime(handleRealtimeEvent, !!user?.id);

  const loadMore = async () => {
    if (!nextPage || loadingMore) return;
    try {
      const url = new URL(nextPage);
      const page = Number(url.searchParams.get("page") || "1");
      await loadFeed({ page, append: true });
    } catch {
      await loadFeed({ page: 1, append: true });
    }
  };

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    const query = searchQuery.trim();
    if (!query) {
      nav("/search");
      return;
    }
    nav(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <div className="social-page feed-page">
      <div className="social-shell with-side-nav feed-shell">
        <aside className="social-side-panel">
          <SocialNav variant="sidebar" />
        </aside>
        <div className="social-main feed-main">
          <div className="social-top">
            <div>
              <div className="social-kicker">Chithi Social</div>
              <h2>Feed</h2>
            </div>

            <form className="feed-search-form feed-header-search" onSubmit={handleSearchSubmit}>
              <span className="feed-search-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <circle cx="11" cy="11" r="6.5" />
                  <path d="m16 16 4 4" />
                </svg>
              </span>
              <input
                type="text"
                className="feed-search-input"
                placeholder="Search Chithi"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="feed-search-submit" aria-label="Search">
                Search
              </button>
            </form>
          </div>

          <CreatePostComposer onCreated={handlePostCreated} />

          {loading ? (
            <div className="social-state">Loading feed...</div>
          ) : error ? (
            <div className="social-state error">
              <p>{error}</p>
              <button type="button" className="social-action-btn" onClick={() => loadFeed({ page: 1, append: false })}>
                Retry
              </button>
            </div>
          ) : posts.length === 0 ? (
            <div className="social-state">No posts yet. Start the conversation.</div>
          ) : (
            <div className="social-list">
              {posts.map((post) => (
                <PostCard
                  key={post.id}
                  post={post}
                  currentUserId={user?.id}
                  onPostUpdated={handlePostUpdated}
                  onPostRemoved={handlePostRemoved}
                />
              ))}
              {nextPage && (
                <button type="button" className="social-load-btn" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? "Loading..." : "Load more"}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

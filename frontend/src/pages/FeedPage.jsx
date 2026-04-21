import React, { useCallback, useEffect, useState } from "react";
import { getFeed } from "../services/api";
import { useAuth } from "../context/AuthContext";
import SocialNav from "../components/SocialNav";
import CreatePostComposer from "../components/CreatePostComposer";
import PostCard from "../components/PostCard";

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
  const { user } = useAuth();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [nextPage, setNextPage] = useState(null);

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

  return (
    <div className="social-page">
      <div className="social-shell">
        <div className="social-top">
          <div>
            <div className="social-kicker">Chithi Social</div>
            <h2>Feed</h2>
          </div>
          <SocialNav />
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
  );
}

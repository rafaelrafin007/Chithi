import React, { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import SocialNav from "../components/SocialNav";
import PostCard from "../components/PostCard";
import { searchPosts, searchUsers } from "../services/api";
import { useAuth } from "../context/AuthContext";

function normalizePaged(payload) {
  if (Array.isArray(payload)) return { results: payload, next: null };
  if (payload && Array.isArray(payload.results)) {
    return { results: payload.results, next: payload.next || null };
  }
  return { results: [], next: null };
}

function displayName(user) {
  return user?.display_name || user?.username || "Unknown";
}

export default function SearchPage() {
  const nav = useNavigate();
  const location = useLocation();
  const [, setSearchParams] = useSearchParams();
  const { user } = useAuth();

  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [users, setUsers] = useState([]);
  const [posts, setPosts] = useState([]);
  const [usersNextPage, setUsersNextPage] = useState(null);
  const [postsNextPage, setPostsNextPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingUsersMore, setLoadingUsersMore] = useState(false);
  const [loadingPostsMore, setLoadingPostsMore] = useState(false);
  const [usersError, setUsersError] = useState("");
  const [postsError, setPostsError] = useState("");

  useEffect(() => {
    const theme = localStorage.getItem("theme") || "dark";
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
  }, []);

  const loadUsers = useCallback(async ({ q = "", page = 1, append = false } = {}) => {
    if (append) setLoadingUsersMore(true);
    setUsersError("");
    try {
      const { data } = await searchUsers({ q, page });
      const normalized = normalizePaged(data);
      setUsers((prev) => (append ? [...prev, ...normalized.results] : normalized.results));
      setUsersNextPage(normalized.next);
      return normalized;
    } catch (err) {
      const message = err?.response?.data?.detail || "Unable to search users.";
      setUsersError(message);
      if (!append) setUsers([]);
      return normalizePaged(null);
    } finally {
      setLoadingUsersMore(false);
    }
  }, []);

  const loadPosts = useCallback(async ({ q = "", page = 1, append = false } = {}) => {
    if (append) setLoadingPostsMore(true);
    setPostsError("");
    try {
      const { data } = await searchPosts({ q, page });
      const normalized = normalizePaged(data);
      setPosts((prev) => (append ? [...prev, ...normalized.results] : normalized.results));
      setPostsNextPage(normalized.next);
      return normalized;
    } catch (err) {
      const message = err?.response?.data?.detail || "Unable to load public posts.";
      setPostsError(message);
      if (!append) setPosts([]);
      return normalizePaged(null);
    } finally {
      setLoadingPostsMore(false);
    }
  }, []);

  const runSearch = useCallback(
    async (q) => {
      setLoading(true);
      await Promise.all([loadUsers({ q, page: 1, append: false }), loadPosts({ q, page: 1, append: false })]);
      setLoading(false);
    },
    [loadPosts, loadUsers]
  );

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const qFromUrl = (params.get("q") || "").trim();
    setQuery(qFromUrl);
    setActiveQuery(qFromUrl);
    runSearch(qFromUrl);
  }, [location.search, runSearch]);

  const handleSearchSubmit = (event) => {
    event.preventDefault();
    const nextQuery = query.trim();
    if (!nextQuery) {
      setSearchParams({});
      return;
    }
    setSearchParams({ q: nextQuery });
  };

  const loadMoreUsers = async () => {
    if (!usersNextPage || loadingUsersMore) return;
    try {
      const url = new URL(usersNextPage);
      const page = Number(url.searchParams.get("page") || "1");
      await loadUsers({ q: activeQuery, page, append: true });
    } catch {
      await loadUsers({ q: activeQuery, page: 1, append: true });
    }
  };

  const loadMorePosts = async () => {
    if (!postsNextPage || loadingPostsMore) return;
    try {
      const url = new URL(postsNextPage);
      const page = Number(url.searchParams.get("page") || "1");
      await loadPosts({ q: activeQuery, page, append: true });
    } catch {
      await loadPosts({ q: activeQuery, page: 1, append: true });
    }
  };

  const handlePostUpdated = (postId, patch) => {
    setPosts((prev) => prev.map((item) => (item.id === postId ? { ...item, ...patch } : item)));
  };

  const handlePostRemoved = (postId) => {
    setPosts((prev) => prev.filter((item) => item.id !== postId));
  };

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
              <h2>Search</h2>
            </div>
          </div>

          <section className="social-card">
            <form className="search-form" onSubmit={handleSearchSubmit}>
              <input
                type="text"
                className="comment-input search-input"
                placeholder="Search users or public posts..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button type="submit" className="social-action-btn">
                Search
              </button>
            </form>
          </section>

          <section className="social-card">
            <h3 className="social-card-title">
              {activeQuery ? `People matching "${activeQuery}"` : "People"}
            </h3>
            {loading ? (
              <div className="social-state">Searching users...</div>
            ) : usersError ? (
              <div className="social-inline-error">{usersError}</div>
            ) : users.length === 0 ? (
              <div className="social-state">No users found.</div>
            ) : (
              <div className="search-user-list">
                {users.map((item) => {
                  const identifier = item.username || item.id;
                  return (
                    <div key={item.id} className="search-user-row">
                      <button
                        type="button"
                        className="notification-actor-link"
                        onClick={() => nav(`/profile/${identifier}`)}
                      >
                        {item.avatar_url ? (
                          <img src={item.avatar_url} alt={displayName(item)} className="post-avatar" />
                        ) : (
                          <div className="post-avatar fallback">{displayName(item).charAt(0).toUpperCase()}</div>
                        )}
                        <div>
                          <div>{displayName(item)}</div>
                          <div className="post-time">@{item.username}</div>
                        </div>
                      </button>
                      {item.is_following && <span className="friends-chip">Following</span>}
                    </div>
                  );
                })}
                {usersNextPage && (
                  <button type="button" className="social-load-btn" onClick={loadMoreUsers} disabled={loadingUsersMore}>
                    {loadingUsersMore ? "Loading..." : "Load more users"}
                  </button>
                )}
              </div>
            )}
          </section>

          <section className="social-card">
            <h3 className="social-card-title">
              {activeQuery ? `Public posts matching "${activeQuery}"` : "Recent public posts"}
            </h3>
            {loading ? (
              <div className="social-state">Loading posts...</div>
            ) : postsError ? (
              <div className="social-inline-error">{postsError}</div>
            ) : posts.length === 0 ? (
              <div className="social-state">No public posts found.</div>
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
                {postsNextPage && (
                  <button type="button" className="social-load-btn" onClick={loadMorePosts} disabled={loadingPostsMore}>
                    {loadingPostsMore ? "Loading..." : "Load more posts"}
                  </button>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

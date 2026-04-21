import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getProfilePosts, getSocialProfile } from "../services/api";
import SocialNav from "../components/SocialNav";
import FollowButton from "../components/FollowButton";
import PostCard from "../components/PostCard";
import ProfilePanel from "./ProfilePanel";

function normalizePaged(payload) {
  if (Array.isArray(payload)) return { results: payload, next: null };
  if (payload && Array.isArray(payload.results)) {
    return { results: payload.results, next: payload.next || null };
  }
  return { results: [], next: null };
}

export default function ProfilePage() {
  const { identifier } = useParams();
  const { user } = useAuth();

  const [profile, setProfile] = useState(null);
  const [posts, setPosts] = useState([]);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [loadingPosts, setLoadingPosts] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [nextPage, setNextPage] = useState(null);
  const [showEditor, setShowEditor] = useState(false);

  useEffect(() => {
    const theme = localStorage.getItem("theme") || "dark";
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
  }, []);

  const isOwnProfile = useMemo(() => {
    if (!profile || !user) return false;
    return profile.id === user.id;
  }, [profile, user]);

  const fetchProfile = useCallback(async () => {
    setLoadingProfile(true);
    setError("");
    try {
      const { data } = await getSocialProfile(identifier);
      setProfile(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Unable to load this profile.");
    } finally {
      setLoadingProfile(false);
    }
  }, [identifier]);

  const fetchPosts = useCallback(async ({ page = 1, append = false } = {}) => {
    if (!append) setLoadingPosts(true);
    else setLoadingMore(true);
    setError("");
    try {
      const { data } = await getProfilePosts(identifier, { page });
      const normalized = normalizePaged(data);
      setPosts((prev) => (append ? [...prev, ...normalized.results] : normalized.results));
      setNextPage(normalized.next);
    } catch (err) {
      setError(err?.response?.data?.detail || "Unable to load profile posts.");
    } finally {
      setLoadingPosts(false);
      setLoadingMore(false);
    }
  }, [identifier]);

  useEffect(() => {
    setProfile(null);
    setPosts([]);
    setNextPage(null);
    fetchProfile();
    fetchPosts({ page: 1, append: false });
  }, [identifier, fetchProfile, fetchPosts]);

  const handleFollowChange = (isFollowing, followerDelta) => {
    setProfile((prev) =>
      prev
        ? {
            ...prev,
            is_following: isFollowing,
            followers_count: Math.max(0, (prev.followers_count || 0) + followerDelta),
          }
        : prev
    );
  };

  const handlePostUpdated = (postId, patch) => {
    setPosts((prev) => prev.map((item) => (item.id === postId ? { ...item, ...patch } : item)));
  };

  const handlePostRemoved = (postId) => {
    setPosts((prev) => prev.filter((item) => item.id !== postId));
  };

  const loadMorePosts = async () => {
    if (!nextPage || loadingMore) return;
    try {
      const url = new URL(nextPage);
      const page = Number(url.searchParams.get("page") || "1");
      await fetchPosts({ page, append: true });
    } catch {
      await fetchPosts({ page: 1, append: true });
    }
  };

  return (
    <div className="social-page">
      <div className="social-shell">
        <div className="social-top">
          <div>
            <div className="social-kicker">Chithi Social</div>
            <h2>Profile</h2>
          </div>
          <SocialNav />
        </div>

        {loadingProfile ? (
          <div className="social-state">Loading profile...</div>
        ) : error && !profile ? (
          <div className="social-state error">
            <p>{error}</p>
            <button type="button" className="social-action-btn" onClick={fetchProfile}>
              Retry
            </button>
          </div>
        ) : profile ? (
          <section className="social-card profile-hero">
            <div className="profile-hero-main">
              {profile.avatar_url ? (
                <img src={profile.avatar_url} alt={profile.display_name} className="profile-hero-avatar" />
              ) : (
                <div className="profile-hero-avatar fallback">
                  {(profile.display_name || profile.username || "U").charAt(0).toUpperCase()}
                </div>
              )}
              <div className="profile-hero-text">
                <h3>{profile.display_name || profile.username}</h3>
                <p>@{profile.username}</p>
                <p>{profile.about || "No bio yet."}</p>
              </div>
            </div>

            <div className="profile-hero-side">
              <div className="profile-counts">
                <span>{profile.followers_count || 0} followers</span>
                <span>{profile.following_count || 0} following</span>
              </div>
              {isOwnProfile ? (
                <button type="button" className="social-action-btn" onClick={() => setShowEditor(true)}>
                  Edit profile
                </button>
              ) : (
                <FollowButton
                  identifier={identifier}
                  isFollowing={!!profile.is_following}
                  onChange={handleFollowChange}
                />
              )}
            </div>
          </section>
        ) : null}

        {loadingPosts ? (
          <div className="social-state">Loading posts...</div>
        ) : posts.length === 0 ? (
          <div className="social-state">No posts to show.</div>
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
              <button type="button" className="social-load-btn" onClick={loadMorePosts} disabled={loadingMore}>
                {loadingMore ? "Loading..." : "Load more"}
              </button>
            )}
          </div>
        )}
      </div>

      {showEditor && (
        <div className="profile-panel-backdrop" onClick={() => setShowEditor(false)}>
          <div className="profile-panel-overlay" onClick={(e) => e.stopPropagation()}>
            <ProfilePanel onClose={() => setShowEditor(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

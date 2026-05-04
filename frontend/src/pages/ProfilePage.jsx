import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { blockUser, getProfilePosts, getSocialProfile, reportUser, unblockUser } from "../services/api";
import SocialNav from "../components/SocialNav";
import FollowButton from "../components/FollowButton";
import PostCard from "../components/PostCard";
import ProfilePanel from "./ProfilePanel";
import useSocialRealtime from "../hooks/useSocialRealtime";

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
  const [blockLoading, setBlockLoading] = useState(false);
  const [blockError, setBlockError] = useState("");
  const [reporting, setReporting] = useState(false);
  const [reportMessage, setReportMessage] = useState("");

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

  const handleBlockToggle = async () => {
    if (!profile || blockLoading) return;
    const targetIdentifier = profile.username || profile.id;
    setBlockLoading(true);
    setBlockError("");
    setReportMessage("");
    try {
      if (profile.is_blocked_by_me) {
        await unblockUser(targetIdentifier);
        setProfile((prev) => (prev ? { ...prev, is_blocked_by_me: false } : prev));
      } else {
        await blockUser(targetIdentifier);
        setProfile((prev) =>
          prev
            ? {
                ...prev,
                is_blocked_by_me: true,
                is_following: false,
              }
            : prev
        );
        setPosts([]);
        setNextPage(null);
      }
    } catch (err) {
      setBlockError(err?.response?.data?.detail || "Unable to update block status.");
    } finally {
      setBlockLoading(false);
    }
  };

  const handleReportUser = async () => {
    if (!profile || reporting) return;
    const reason = window.prompt("Reason for report (e.g. spam, abuse)", "abuse");
    if (!reason) return;
    const details = window.prompt("Additional details (optional)", "") || "";
    setReporting(true);
    setBlockError("");
    setReportMessage("");
    try {
      const targetIdentifier = profile.username || profile.id;
      await reportUser(targetIdentifier, { reason, details });
      setReportMessage("Report submitted.");
    } catch (err) {
      setBlockError(err?.response?.data?.detail || "Unable to submit report.");
    } finally {
      setReporting(false);
    }
  };

  const handleRealtimeEvent = useCallback(
    (payload) => {
      const eventName = payload?.event;
      if (!eventName) return;

      if (eventName === "post_created" && payload.post) {
        if (!profile || payload.post.author?.id !== profile.id) return;
        const alreadyInList = posts.some((item) => item.id === payload.post.id);
        setPosts((prev) => {
          const exists = prev.some((item) => item.id === payload.post.id);
          if (exists) {
            return prev.map((item) => (item.id === payload.post.id ? { ...item, ...payload.post } : item));
          }
          return [payload.post, ...prev];
        });
        if (!alreadyInList) {
          setProfile((prev) =>
            prev ? { ...prev, posts_count: (prev.posts_count || 0) + 1 } : prev
          );
        }
        return;
      }

      if (eventName === "post_updated" && payload.post_id) {
        setPosts((prev) =>
          prev.map((item) => (item.id === payload.post_id ? { ...item, ...(payload.post || {}) } : item))
        );
        return;
      }

      if (eventName === "post_deleted" && payload.post_id) {
        const hadPostInList = posts.some((item) => item.id === payload.post_id);
        if (hadPostInList) {
          setProfile((prevProfile) =>
            prevProfile
              ? { ...prevProfile, posts_count: Math.max(0, (prevProfile.posts_count || 0) - 1) }
              : prevProfile
          );
        }
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
    [posts, profile, user?.id]
  );

  useSocialRealtime(handleRealtimeEvent, !!user?.id);

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
      <div className="social-shell with-side-nav">
        <aside className="social-side-panel">
          <SocialNav variant="sidebar" />
        </aside>
        <div className="social-main">
          <div className="social-top">
            <div>
              <div className="social-kicker">Chithi Social</div>
              <h2>Profile</h2>
            </div>
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
                <div className="profile-safety-actions">
                  {!profile.is_blocked_by_me && !profile.has_blocked_me && (
                    <FollowButton
                      identifier={identifier}
                      isFollowing={!!profile.is_following}
                      onChange={handleFollowChange}
                    />
                  )}
                  <button type="button" className="social-action-btn secondary" onClick={handleBlockToggle} disabled={blockLoading}>
                    {blockLoading ? "Please wait..." : profile.is_blocked_by_me ? "Unblock" : "Block"}
                  </button>
                  <button type="button" className="social-link-btn" onClick={handleReportUser} disabled={reporting}>
                    {reporting ? "Reporting..." : "Report user"}
                  </button>
                  {profile.has_blocked_me && <div className="social-inline-error">You are blocked by this user.</div>}
                  {blockError && <div className="social-inline-error">{blockError}</div>}
                  {reportMessage && <div className="social-inline-success">{reportMessage}</div>}
                </div>
              )}
            </div>
            </section>
          ) : null}

          {loadingPosts ? (
            <div className="social-state">Loading posts...</div>
          ) : error && posts.length === 0 ? (
            <div className="social-state">{error}</div>
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

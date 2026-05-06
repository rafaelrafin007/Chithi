// src/pages/Friends.jsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import SocialNav from "../components/SocialNav";
import FollowButton from "../components/FollowButton";
import {
  getUsersDirectory,
  getFriendRequests,
  sendFriendRequest,
  respondFriendRequest,
  cancelFriendRequest,
  unblockUser,
  openConversation,
} from "../services/api";

export default function Friends() {
  const [searchQuery, setSearchQuery] = useState("");
  const [users, setUsers] = useState([]);
  const [incoming, setIncoming] = useState([]);
  const [outgoing, setOutgoing] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState("");
  const [openingInboxUserId, setOpeningInboxUserId] = useState(null);
  const nav = useNavigate();

  useEffect(() => {
    const theme = localStorage.getItem("theme") || "dark";
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [usersResp, reqResp] = await Promise.all([getUsersDirectory(), getFriendRequests()]);
      setUsers(usersResp.data || []);
      setIncoming(reqResp.data?.incoming || []);
      setOutgoing(reqResp.data?.outgoing || []);
    } catch (e) {
      console.error("Failed to load friends data", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSend = async (userId) => {
    try {
      setActionError("");
      await sendFriendRequest(userId);
      await load();
    } catch (e) {
      setActionError(e?.response?.data?.detail || "Failed to send friend request.");
    }
  };

  const handleRespond = async (requestId, action) => {
    try {
      setActionError("");
      await respondFriendRequest(requestId, action);
      await load();
    } catch (e) {
      setActionError(e?.response?.data?.detail || "Failed to respond to request.");
    }
  };

  const handleCancel = async (requestId) => {
    try {
      setActionError("");
      await cancelFriendRequest(requestId);
      await load();
    } catch (e) {
      setActionError(e?.response?.data?.detail || "Failed to cancel request.");
    }
  };

  const handleFollowChanged = (userId, nextFollowing) => {
    setUsers((prev) =>
      prev.map((item) =>
        item.id === userId ? { ...item, is_following: nextFollowing } : item
      )
    );
  };

  const handleUnblock = async (identifier, userId) => {
    try {
      setActionError("");
      await unblockUser(identifier);
      setUsers((prev) =>
        prev.map((item) =>
          item.id === userId
            ? { ...item, is_blocked_by_me: false, friend_status: item.has_blocked_me ? "blocked_by_them" : "none" }
            : item
        )
      );
    } catch (e) {
      setActionError(e?.response?.data?.detail || "Failed to unblock user.");
    }
  };

  const canShowInboxButton = (u) => {
    if (!u) return false;
    if (u.is_blocked_by_me || u.has_blocked_me) return false;
    return u.friend_status === "friends";
  };

  const handleOpenInbox = async (u) => {
    try {
      setActionError("");
      setOpeningInboxUserId(u.id);
      await openConversation(u.id);
      nav("/chat", { state: { openConversationUserId: u.id } });
    } catch (e) {
      setActionError(e?.response?.data?.detail || "Unable to open inbox for this user.");
    } finally {
      setOpeningInboxUserId(null);
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
    <div className="social-page">
      <div className="social-shell with-side-nav feed-shell">
        <aside className="social-side-panel">
          <SocialNav variant="sidebar" />
        </aside>

        <div className="social-main feed-main">
          <div className="social-top">
            <div>
              <div className="social-kicker">Network</div>
              <h2>Friends</h2>
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

          {loading ? (
            <p className="friends-muted">Loading...</p>
          ) : (
            <div className="friends-grid">
              {actionError && <div className="friends-inline-error">{actionError}</div>}
              <section className="friends-card">
                <div className="friends-card-title">Incoming Requests</div>
                {incoming.length === 0 && <p className="friends-muted">No incoming requests.</p>}
                {incoming.map((r) => (
                  <div key={r.id} className="friends-row">
                    <div className="friends-user">
                      <div className="friends-name">{r.from_user?.display_name || r.from_user?.username}</div>
                    </div>
                    <div className="friends-actions">
                      <button className="btn btn-primary" onClick={() => handleRespond(r.id, "accept")}>
                        Accept
                      </button>
                      <button className="btn btn-secondary" onClick={() => handleRespond(r.id, "decline")}>
                        Decline
                      </button>
                    </div>
                  </div>
                ))}
              </section>

              <section className="friends-card">
                <div className="friends-card-title">Outgoing Requests</div>
                {outgoing.length === 0 && <p className="friends-muted">No outgoing requests.</p>}
                {outgoing.map((r) => (
                  <div key={r.id} className="friends-row">
                    <div className="friends-user">
                      <div className="friends-name">{r.to_user?.display_name || r.to_user?.username}</div>
                      <div className="friends-meta">Pending</div>
                    </div>
                    <div className="friends-actions">
                      <button className="btn btn-secondary" onClick={() => handleCancel(r.id)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ))}
              </section>

              <section className="friends-card friends-card-wide">
                <div className="friends-card-title">All Users</div>
                {users.map((u) => (
                  <div key={u.id} className="friends-row">
                    <div className="friends-user">
                      <div className="friends-name">
                        {u.display_name || u.username}
                        <span className="friends-id">#{u.id}</span>
                      </div>
                      {u.is_blocked_by_me && <div className="friends-meta blocked">Blocked</div>}
                      {u.has_blocked_me && <div className="friends-meta danger">Blocked you</div>}
                      {!u.is_blocked_by_me && !u.has_blocked_me && u.friend_status === "friends" && <div className="friends-meta success">Friends</div>}
                      {!u.is_blocked_by_me && !u.has_blocked_me && u.friend_status === "incoming" && <div className="friends-meta warn">Requested you</div>}
                      {!u.is_blocked_by_me && !u.has_blocked_me && u.friend_status === "outgoing" && <div className="friends-meta">Pending</div>}
                    </div>
                    <div className="friends-actions">
                      {u.is_blocked_by_me ? (
                        <button className="btn btn-secondary" onClick={() => handleUnblock(u.username || u.id, u.id)}>
                          Unblock
                        </button>
                      ) : u.has_blocked_me ? (
                        <span className="friends-chip blocked">Unavailable</span>
                      ) : (
                        <>
                          <FollowButton
                            identifier={u.id}
                            isFollowing={!!u.is_following}
                            onChange={(nextFollowing) => handleFollowChanged(u.id, nextFollowing)}
                          />
                          {u.friend_status === "none" && (
                            <button className="btn btn-primary" onClick={() => handleSend(u.id)}>
                              Add friend
                            </button>
                          )}
                          {u.friend_status === "declined" && (
                            <button className="btn btn-secondary" onClick={() => handleSend(u.id)}>
                              Add again
                            </button>
                          )}
                          {u.friend_status === "outgoing" && (
                            <button
                              className="btn btn-secondary"
                              onClick={() => {
                                const pending = outgoing.find((o) => o.to_user?.id === u.id);
                                if (pending) handleCancel(pending.id);
                              }}
                            >
                              Cancel
                            </button>
                          )}
                          {u.friend_status === "friends" && <span className="friends-chip">Connected</span>}
                          {canShowInboxButton(u) && (
                            <button
                              className="btn btn-secondary"
                              onClick={() => handleOpenInbox(u)}
                              disabled={openingInboxUserId === u.id}
                            >
                              {openingInboxUserId === u.id ? "Opening..." : "Inbox"}
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

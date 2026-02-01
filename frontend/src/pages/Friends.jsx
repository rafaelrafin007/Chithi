// src/pages/Friends.jsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getUsersDirectory,
  getFriendRequests,
  sendFriendRequest,
  respondFriendRequest,
  cancelFriendRequest,
} from "../services/api";

export default function Friends() {
  const [users, setUsers] = useState([]);
  const [incoming, setIncoming] = useState([]);
  const [outgoing, setOutgoing] = useState([]);
  const [loading, setLoading] = useState(true);
  const nav = useNavigate();

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
    await sendFriendRequest(userId);
    await load();
  };

  const handleRespond = async (requestId, action) => {
    await respondFriendRequest(requestId, action);
    await load();
  };

  const handleCancel = async (requestId) => {
    await cancelFriendRequest(requestId);
    await load();
  };

  return (
    <div className="friends-page">
      <div className="friends-shell">
        <div className="friends-header">
          <div>
            <div className="friends-kicker">Network</div>
            <h2>Friends</h2>
          </div>
          <button className="btn btn-secondary" onClick={() => nav("/chat")}>
            Back to chat
          </button>
        </div>

        {loading ? (
          <p className="friends-muted">Loading...</p>
        ) : (
          <div className="friends-grid">
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
                    {u.friend_status === "friends" && <div className="friends-meta success">Friends</div>}
                {u.friend_status === "incoming" && <div className="friends-meta warn">Requested you</div>}
                {u.friend_status === "outgoing" && <div className="friends-meta">Pending</div>}
              </div>
              <div className="friends-actions">
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
              </div>
            </div>
          ))}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

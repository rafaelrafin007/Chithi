import React, { useState } from "react";
import { followUser, unfollowUser } from "../services/api";

export default function FollowButton({
  identifier,
  isFollowing,
  disabled = false,
  onChange,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleToggle = async () => {
    if (!identifier || loading || disabled) return;
    setError("");
    setLoading(true);
    const nextFollowing = !isFollowing;

    try {
      if (nextFollowing) await followUser(identifier);
      else await unfollowUser(identifier);
      onChange?.(nextFollowing, nextFollowing ? 1 : -1);
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        (typeof err?.response?.data === "string" ? err.response.data : "") ||
        err?.message ||
        "Failed to update follow status.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="follow-button-wrap">
      <button
        type="button"
        className="social-action-btn"
        onClick={handleToggle}
        disabled={loading || disabled}
      >
        {loading ? "Please wait..." : isFollowing ? "Unfollow" : "Follow"}
      </button>
      {error && <div className="social-inline-error">{error}</div>}
    </div>
  );
}

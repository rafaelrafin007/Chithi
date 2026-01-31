// src/context/AuthContext.jsx
import React, { createContext, useContext, useEffect, useState } from "react";
import api, { getProfile, updateProfile as apiUpdateProfile } from "../services/api";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  const normalizeUser = (u = {}) => {
    const profile = u.profile || {};
    let avatar_url = u.avatar_url || profile.avatar_url || null;
    if (!avatar_url && profile.avatar) {
      avatar_url = typeof profile.avatar === "string" ? profile.avatar : profile.avatar?.url || null;
    }
    const display_name = u.display_name || profile.display_name || null;
    return {
      ...u,
      profile,
      display_name,
      avatar_url,
    };
  };

  // Login accepts { username, password, email } (username field may contain an email)
  const login = async ({ username, password, email } = {}) => {
    try {
      const payload = {};
      if (username) payload.username = username;
      if (email) payload.email = email;
      payload.password = password;

      const { data } = await api.post("/api/auth/login/", payload);
      localStorage.setItem("access", data.access);
      localStorage.setItem("refresh", data.refresh);

      // fetch /me to populate user
      const me = await api.get("/api/auth/me/");
      setUser(normalizeUser(me.data));
      return me.data;
    } catch (err) {
      const serverMessage =
        err?.response?.data ||
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors ||
        err?.response?.data?.message ||
        err?.message ||
        "Login failed";
      throw serverMessage;
    }
  };

  const register = async ({ username, email, password }) => {
    try {
      const { data } = await api.post("/api/auth/register/", {
        username,
        email,
        password,
      });
      // login after register (use username)
      await login({ username, password });
      return data;
    } catch (err) {
      const serverMessage =
        err?.response?.data ||
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors ||
        err?.response?.data?.message ||
        err?.message ||
        "Registration failed";
      throw serverMessage;
    }
  };

  const logout = () => {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    setUser(null);
  };

  // Fetch current user (used by boot and also useful externally)
  const fetchMe = async () => {
    try {
      const { data } = await api.get("/api/auth/me/");
      setUser(normalizeUser(data));
      return data;
    } catch (err) {
      // if unauthorized or failed, clear local tokens
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      setUser(null);
      throw err;
    }
  };

  /**
   * updateProfile(payload, avatarFile)
   * - payload: { display_name, about, phone } (optional)
   * - avatarFile: File | null
   *
   * Uses api.updateProfile which sends PATCH /api/auth/me/
   * Returns the updated user object and updates context.user.
   */
  const updateProfile = async (payload = {}, avatarFile = null) => {
    try {
      const resp = await apiUpdateProfile(payload, avatarFile);
      // backend returns updated user data
      const updated = resp.data;
      setUser(normalizeUser(updated));
      return updated;
    } catch (err) {
      const serverMessage =
        err?.response?.data ||
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors ||
        err?.response?.data?.message ||
        err?.message ||
        "Failed to update profile";
      throw serverMessage;
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      const token = localStorage.getItem("access");
      if (!token) {
        setBooting(false);
        return;
      }
      try {
        await fetchMe();
      } catch {
        // fetchMe already clears tokens on failure
      } finally {
        setBooting(false);
      }
    };
    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        booting,
        login,
        register,
        logout,
        fetchMe,
        updateProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

// src/services/api.js
import axios from "axios";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const apiBaseUrl = (process.env.REACT_APP_API_BASE_URL || DEFAULT_API_BASE).replace(/\/+$/, "");

const api = axios.create({
  baseURL: apiBaseUrl,
});

export const getApiBaseUrl = () => apiBaseUrl;

// Attach JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ---- Chat helper methods (optional, cleaner usage) ----
export const getUsers = () => api.get("/api/chat/users/");
export const getConversation = (userId) => api.get(`/api/chat/conversation/${userId}/`);

/**
 * sendMessage(receiverId, content, file)
 * - if `file` is provided, send multipart/form-data with 'attachment' field
 * - otherwise send JSON body as before
 */
export const sendMessage = (receiverId, content, file = null) => {
  if (file) {
    const fd = new FormData();
    fd.append("receiver", receiverId);
    if (content) fd.append("content", content);
    fd.append("attachment", file);
    return api.post("/api/chat/send/", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  } else {
    return api.post("/api/chat/send/", { receiver: receiverId, content });
  }
};

/* === Profile endpoints === */
export const getProfile = () => api.get("/api/auth/me/");
export const updateProfile = (payload = {}, avatarFile = null) => {
  // payload: { display_name, about, phone } optional
  if (avatarFile) {
    const fd = new FormData();
    if (payload.display_name) fd.append("display_name", payload.display_name);
    if (payload.about) fd.append("about", payload.about);
    if (payload.phone) fd.append("phone", payload.phone);
    fd.append("avatar", avatarFile);
    // PATCH with formdata
    return api.patch("/api/auth/me/", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  } else {
    // JSON patch
    return api.patch("/api/auth/me/", payload);
  }
};

/* === Friends === */
export const getUsersDirectory = () => api.get("/api/auth/users/");
export const getFriendRequests = () => api.get("/api/auth/friend-requests/");
export const sendFriendRequest = (toUserId) => api.post("/api/auth/friend-requests/", { to_user_id: toUserId });
export const respondFriendRequest = (requestId, action) =>
  api.post(`/api/auth/friend-requests/${requestId}/respond/`, { action });
export const cancelFriendRequest = (requestId) =>
  api.post(`/api/auth/friend-requests/${requestId}/cancel/`);
export const getFriends = () => api.get("/api/auth/friends/");

// ---- Token refresh handling ----
let isRefreshing = false;
let refreshQueue = [];

const resolveQueue = (error, token = null) => {
  refreshQueue.forEach((p) => {
    if (error) p.reject(error);
    else p.resolve(token);
  });
  refreshQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (!original || error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }

    const refresh = localStorage.getItem("refresh");
    if (!refresh) {
      return Promise.reject(error);
    }

    const isRefreshRequest = (original.url || "").includes("/api/auth/token/refresh/");
    if (isRefreshRequest) {
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        refreshQueue.push({ resolve, reject });
      })
        .then((token) => {
          original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        })
        .catch((err) => Promise.reject(err));
    }

    original._retry = true;
    isRefreshing = true;
    try {
      const { data } = await axios.post(`${apiBaseUrl}/api/auth/token/refresh/`, { refresh });
      localStorage.setItem("access", data.access);
      api.defaults.headers.common.Authorization = `Bearer ${data.access}`;
      resolveQueue(null, data.access);
      return api(original);
    } catch (err) {
      resolveQueue(err, null);
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      return Promise.reject(err);
    } finally {
      isRefreshing = false;
    }
  }
);

export default api;

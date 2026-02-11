// src/hooks/useChat.js
import { useEffect, useState, useRef, useCallback } from "react";
import api, { sendMessage, getApiBaseUrl } from "../services/api";

/**
 * useChat(user)
 * Encapsulates all chat state + websocket lifecycle + message actions.
 *
 * NOTE: PDF thumbnailing is attempted via dynamic imports of pdfjs-dist.
 * If you want PDF thumbnails, install: `npm install pdfjs-dist`
 */

export default function useChat(user) {
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "dark");
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [typing, setTyping] = useState(false);

  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const lastTypingSentRef = useRef(0);
  const deliveredAcksRef = useRef(new Set());

  // Attachment states
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null); // dataURL or objectURL or null

  // UI state for message menu / editing
  const [menuOpenFor, setMenuOpenFor] = useState(null);
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editingText, setEditingText] = useState("");

  const showDesktopNotification = useCallback((msg) => {
    if (!msg || !msg.sender) return;
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
      return;
    }
    if (Notification.permission !== "granted") return;
    if (!document.hidden) return;
    const title = msg.sender?.display_name || msg.sender?.username || "New message";
    const body = msg.content || (msg.attachment_url ? "Sent an attachment" : "New message");
    try {
      new Notification(title, {
        body,
        tag: `chat-${msg.sender?.id || "unknown"}`,
        icon: msg.sender?.avatar_url || undefined,
      });
    } catch {
      /* ignore */
    }
  }, []);

  const showFriendRequestNotification = useCallback((fromUser) => {
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
      return;
    }
    if (Notification.permission !== "granted") return;
    if (!document.hidden) return;
    const title = "New friend request";
    const body = `${fromUser?.display_name || fromUser?.username || "Someone"} sent you a friend request`;
    try {
      new Notification(title, {
        body,
        tag: `friend-request-${fromUser?.id || "unknown"}`,
        icon: fromUser?.avatar_url || undefined,
      });
    } catch {
      /* ignore */
    }
  }, []);

  const sendReaction = (messageId, emoji) => {
    if (!messageId || !emoji) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "react", message_id: messageId, emoji }));
    }
  };

  // ----- Helpers -----
  const normalizeUser = (u = {}) => {
    // Defensive normalization: support several backends shapes
    const profile = u.profile || {};
    // avatar may be a URL string or an object with .url depending on serializer
    let avatar_url = u.avatar_url || profile.avatar_url || null;
    if (!avatar_url && profile.avatar) {
      // profile.avatar might be a string or { url: ... }
      avatar_url = typeof profile.avatar === "string" ? profile.avatar : profile.avatar?.url || null;
    }
    const display_name = u.display_name || profile.display_name || null;
    return {
      ...u,
      profile: profile,
      display_name,
      avatar_url,
    };
  };

  // Save selected to localStorage
  useEffect(() => {
    if (selected) localStorage.setItem("selectedUserId", selected.id);
  }, [selected]);

  // Theme side-effect
  useEffect(() => {
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(theme + "-theme");
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  // --- Fetch Users ---
  const fetchUsers = useCallback(async () => {
    try {
      const { data } = await api.get("/api/chat/users/");
      // Normalize incoming users
      const normalized = (Array.isArray(data) ? data : []).map(normalizeUser);
      const sorted = [...normalized].sort((a, b) => {
        const aTime = new Date(a.last_message?.timestamp || 0).getTime();
        const bTime = new Date(b.last_message?.timestamp || 0).getTime();
        return bTime - aTime;
      });

      const savedId = localStorage.getItem("selectedUserId");
      let initialSelected = null;
      if (savedId) {
        initialSelected = sorted.find((u) => u.id?.toString() === savedId);
      }
      if (!selected) setSelected(initialSelected || (sorted.length ? sorted[0] : null));
      setUsers(sorted.map((u) => ({ ...u, unread: u.unread || 0, is_online: u.is_online || false })));
    } catch (err) {
      console.error("Error fetching users:", err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  // --- Format Timestamp ---
  const formatTimestamp = useCallback((timestamp) => {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    const now = new Date();

    const isToday = date.toDateString() === now.toDateString();
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = date.toDateString() === yesterday.toDateString();

    if (isToday)
      return `Today ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    if (isYesterday)
      return `Yesterday ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }, []);

  // --- Safe send with retry ---
  const sendWhenWsReady = (obj) => {
    if (!wsRef.current) return;
    if (wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(obj));
      return;
    }
    const onOpen = () => {
      try {
        wsRef.current.send(JSON.stringify(obj));
      } catch (e) {
        /* ignore */
      } finally {
        try {
          wsRef.current.removeEventListener("open", onOpen);
        } catch {}
      }
    };
    try {
      wsRef.current.addEventListener("open", onOpen);
      setTimeout(() => {
        try {
          wsRef.current.removeEventListener("open", onOpen);
        } catch {}
      }, 3000);
    } catch (e) {
      /* ignore */
    }
  };

  // --- Generate PDF thumbnail (unchanged) ---
  const generatePdfThumbnail = async (file, { scale = 1.0 } = {}) => {
    try {
      let pdfjs = null;
      const tryImports = [
        "pdfjs-dist/legacy/build/pdf",
        "pdfjs-dist/build/pdf",
        "pdfjs-dist",
      ];
      for (const path of tryImports) {
        try {
          // eslint-disable-next-line no-await-in-loop
          const mod = await import(/* webpackChunkName: "pdfjs" */ path);
          if (mod) {
            pdfjs = mod;
            break;
          }
        } catch (e) {
          // try next
        }
      }
      if (!pdfjs || !pdfjs.getDocument) {
        console.warn("pdfjs not available for thumbnail generation.");
        return null;
      }
      try {
        if (pdfjs.GlobalWorkerOptions) {
          pdfjs.GlobalWorkerOptions.workerSrc =
            "//cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js";
        }
      } catch (e) {}
      const url = URL.createObjectURL(file);
      const loadingTask = pdfjs.getDocument({ url });
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(1);
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      canvas.width = Math.round(viewport.width);
      canvas.height = Math.round(viewport.height);
      const renderTask = page.render({ canvasContext: ctx, viewport });
      if (renderTask && renderTask.promise) {
        await renderTask.promise;
      } else {
        await renderTask;
      }
      const dataUrl = canvas.toDataURL("image/png");
      try {
        loadingTask.destroy?.();
      } catch {}
      try {
        URL.revokeObjectURL(url);
      } catch {}
      return dataUrl;
    } catch (err) {
      console.error("PDF thumbnail generation failed:", err);
      return null;
    }
  };

  // --- Fetch Conversation ---
  const fetchConversation = useCallback(async () => {
    if (!selected) return;
    try {
      const { data } = await api.get(`/api/chat/conversation/${selected.id}/`);
      setMessages(data);
      scrollToBottom();

      if (data.length) {
        const lastTs = data[data.length - 1].timestamp;
        sendWhenWsReady({ type: "read", last_read: lastTs });
      }

      setUsers((prev) => prev.map((u) => (u.id === selected.id ? { ...u, unread: 0 } : u)));
    } catch (err) {
      console.error("Error fetching conversation:", err);
    }
  }, [selected]);

  // --- WebSocket lifecycle ---
  useEffect(() => {
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {}
      wsRef.current = null;
    }

    if (!selected?.id || !user?.id) return;

    const token = localStorage.getItem("access");
    if (!token) return;

    let cancelled = false;
    const connect = async () => {
      try {
        const resp = await api.get("/api/chat/ws-token/");
        const wsToken = resp.data?.ws_token;
        if (!wsToken || cancelled) return;

        const apiBase = getApiBaseUrl();
        const wsScheme = apiBase.startsWith("https://") ? "wss" : "ws";
        const wsHost = apiBase.replace(/^https?:\/\//, "");
        const url = `${wsScheme}://${wsHost}/ws/chat/${selected.id}/?ws_token=${encodeURIComponent(wsToken)}`;

        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (messages.length) {
            const lastTs = messages[messages.length - 1].timestamp;
            sendWhenWsReady({ type: "read", last_read: lastTs });
          }
        };

        ws.onmessage = (evt) => {
          try {
            const payload = JSON.parse(evt.data);

        if (payload?.type === "presence") {
          const { user: presenceUserId, online } = payload;
          if (presenceUserId) {
            setUsers((prev) =>
              prev.map((u) => (u.id === presenceUserId ? { ...u, is_online: !!online } : u))
            );
            setSelected((prev) =>
              prev && prev.id === presenceUserId ? { ...prev, is_online: !!online } : prev
            );
          }
          return;
        }

        if (payload?.type === "presence_sync" && Array.isArray(payload.users)) {
          const onlineSet = new Set(payload.users);
          setUsers((prev) => prev.map((u) => ({ ...u, is_online: onlineSet.has(u.id) })));
          setSelected((prev) =>
            prev ? { ...prev, is_online: onlineSet.has(prev.id) } : prev
          );
          return;
        }

        if (payload?.type === "friend_request") {
          showFriendRequestNotification(payload.from_user);
          return;
        }

        if (payload?.type === "typing") {
          const typingUserId = payload.user;
          if (typingUserId && typingUserId !== user?.id && typingUserId === selected?.id) {
            setTyping(true);
            clearTimeout(typingTimeoutRef.current);
            typingTimeoutRef.current = setTimeout(() => setTyping(false), 1500);
          }
          return;
        }

        if (payload?.type === "delivered") {
          const { user: ackUserId, message_id } = payload;
          if (ackUserId && ackUserId !== user?.id && message_id) {
            setMessages((prev) => prev.map((m) => (m.id === message_id ? { ...m, delivered: true } : m)));
          }
          return;
        }

        if (payload?.type === "read") {
          const { user: readerId, last_read } = payload;
          if (readerId && readerId !== user?.id && last_read) {
            const lr = new Date(last_read).getTime();
            setMessages((prev) =>
              prev.map((m) =>
                m.sender?.id === user?.id && new Date(m.timestamp).getTime() <= lr
                  ? { ...m, read: true, delivered: true }
                  : m
              )
            );
          }
          return;
        }

        // Sidebar update: update user's last message + unread
        if (payload?.type === "sidebar" && payload?.data) {
          const msg = payload.data;
          // participant is the other user in the message (sender or receiver)
          const participant = msg.sender?.id === user?.id ? msg.receiver : msg.sender;
          const norm = normalizeUser(participant);
          const targetId = norm.id;
          setUsers((prev) => {
            const existing = prev.find((u) => u.id === targetId) || {};
            const others = prev.filter((u) => u.id !== targetId);
            const isActive = selected?.id === targetId;
            return [
              {
                ...existing,
                ...norm,
                last_message: msg,
                unread: isActive ? 0 : (existing.unread || 0) + (msg.sender?.id !== user?.id ? 1 : 0),
              },
              ...others,
            ];
          });
          return;
        }

        // New incoming message
        if (payload?.type === "message" && payload?.data) {
          const msg = payload.data;

          // --- FIX: clear typing indicator when a real message arrives from the selected user
          if (msg.sender?.id === selected?.id) {
            setTyping(false);
            clearTimeout(typingTimeoutRef.current);
          }

          const participant = msg.sender?.id === user?.id ? msg.receiver : msg.sender;
          const norm = normalizeUser(participant);
          const targetId = norm.id;

          setUsers((prev) => {
            const others = prev.filter((u) => u.id !== targetId);
            const existing = prev.find((u) => u.id === targetId) || {};
            const isActive = selected?.id === targetId;
            return [
              {
                ...existing,
                ...norm,
                last_message: msg,
                unread: isActive ? 0 : (existing.unread || 0) + (msg.sender?.id !== user?.id ? 1 : 0),
              },
              ...others,
            ];
          });

          if (
            (msg.sender?.id === user?.id && msg.receiver?.id === selected?.id) ||
            (msg.sender?.id === selected?.id && msg.receiver?.id === user?.id)
          ) {
            setMessages((prev) => (prev.some((p) => p.id === msg.id) ? prev : [...prev, msg]));
            if (msg.receiver?.id === user?.id && msg.id && !deliveredAcksRef.current.has(msg.id)) {
              deliveredAcksRef.current.add(msg.id);
              sendWhenWsReady({ type: "delivered", message_id: msg.id });
            }
            if (msg.sender?.id !== user?.id) {
              showDesktopNotification(msg);
            }
            scrollToBottom();
          }
          return;
        }

        // message_updated
        if (payload?.type === "message_updated" && payload?.data) {
          const updated = payload.data;
          setMessages((prev) => prev.map((m) => (m.id === updated.id ? { ...m, ...updated } : m)));
          setUsers((prev) =>
            prev.map((u) =>
              u.last_message && u.last_message.id === updated.id ? { ...u, last_message: updated } : u
            )
          );
          return;
        }

        if (payload?.type === "reaction") {
          const { message_id, emoji, user: reactorId, action } = payload;
          if (!message_id || !emoji || !reactorId) return;
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== message_id) return m;
              const reactions = Array.isArray(m.reactions) ? [...m.reactions] : [];
              const idx = reactions.findIndex((r) => r.emoji === emoji);
              if (idx === -1) {
                if (action === "added") {
                  reactions.push({ emoji, count: 1, users: [reactorId] });
                }
              } else {
                const entry = { ...reactions[idx] };
                const users = new Set(entry.users || []);
                if (action === "added") users.add(reactorId);
                if (action === "removed") users.delete(reactorId);
                entry.users = Array.from(users);
                entry.count = entry.users.length;
                if (entry.count === 0) {
                  reactions.splice(idx, 1);
                } else {
                  reactions[idx] = entry;
                }
              }
              return { ...m, reactions };
            })
          );
          return;
        }

        // message_deleted
        if (payload?.type === "message_deleted" && payload?.data) {
          const { id } = payload.data;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id
                ? {
                    ...m,
                    content: "This message was deleted",
                    is_deleted: true,
                    attachment_url: null,
                    attachment_thumb: null,
                    attachment: null,
                  }
                : m
            )
          );
          setUsers((prev) =>
            prev.map((u) =>
              u.last_message && u.last_message.id === id
                ? {
                    ...u,
                    last_message: {
                      ...u.last_message,
                      content: "This message was deleted",
                      is_deleted: true,
                      attachment_url: null,
                      attachment_thumb: null,
                      attachment: null,
                    },
                  }
                : u
            )
          );
          return;
        }
          } catch (e) {
            console.error("WS parse error:", e);
          }
        };

        ws.onclose = () => {};
        ws.onerror = (e) => console.error("WS error:", e);
      } catch (err) {
        console.error("Failed to fetch WS token:", err);
      }
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(typingTimeoutRef.current);
      try {
        ws.close();
      } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id, user?.id, messages.length]);

  // --- Send Message ---
  const send = async () => {
    if ((!text || !text.trim()) && !selectedFile) return;
    const content = text.trim();

    // If there is an attachment -> always send via REST (multipart)
    if (selectedFile) {
      await sendViaRest(content, selectedFile);
      // clear typing locally after sending attachment message
      setTyping(false);
      clearTimeout(typingTimeoutRef.current);
      return;
    }

    // No attachment -> use websocket when available, otherwise REST
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content }));
      setText("");
      // clear typing locally after sending
      setTyping(false);
      clearTimeout(typingTimeoutRef.current);
    } else {
      await sendViaRest(content, null);
      // clear typing locally after REST send
      setTyping(false);
      clearTimeout(typingTimeoutRef.current);
    }
  };

  // send via REST (supports optional file)
  const sendViaRest = async (content, file = null) => {
    try {
      let resp;
      if (file) {
        resp = await sendMessage(selected.id, content, file); // helper in api.js
      } else {
        resp = await api.post("/api/chat/send/", { receiver: selected.id, content });
      }
      const data = resp.data;

      // Deduplicate by id
      setMessages((prev) => (prev.some((p) => p.id === data.id) ? prev : [...prev, data]));

      setUsers((prev) => {
        const reordered = prev.filter((u) => u.id !== selected.id);
        const normSel = normalizeUser(selected || {});
        return [{ ...normSel, last_message: data, unread: 0 }, ...reordered];
      });

      // Clear input & attachment
      setText("");
      removeAttachment();

      scrollToBottom();
    } catch (err) {
      console.error("Error sending via REST:", err);
    }
  };

  // --- Typing ---
  const handleTyping = (e) => {
    setText(e.target.value);
    const now = Date.now();
    if (now - lastTypingSentRef.current < 700) return;
    lastTypingSentRef.current = now;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      sendWhenWsReady({ type: "typing" });
    }
  };

  // --- Attachment handlers ---
  const handleFileChange = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setSelectedFile(f);

    // Images -> object URL preview
    if (f.type && f.type.startsWith("image/")) {
      const url = URL.createObjectURL(f);
      setPreviewUrl(url);
    } else if (f.type === "application/pdf" || (f.name && f.name.toLowerCase().endsWith(".pdf"))) {
      // PDF -> try to generate thumbnail via pdfjs
      try {
        const thumb = await generatePdfThumbnail(f, { scale: 0.8 });
        setPreviewUrl(thumb); // dataURL or null
      } catch (err) {
        console.error("PDF thumb generation error", err);
        setPreviewUrl(null);
      }
    } else {
      // Other files -> no visual thumbnail, show file-card with filename
      setPreviewUrl(null);
    }
    e.target.value = "";
  };

  const removeAttachment = () => {
    if (previewUrl && previewUrl.startsWith("blob:")) {
      try {
        URL.revokeObjectURL(previewUrl);
      } catch {}
    }
    setSelectedFile(null);
    setPreviewUrl(null);
  };

  useEffect(() => {
    return () => {
      if (previewUrl && previewUrl.startsWith("blob:")) {
        try {
          URL.revokeObjectURL(previewUrl);
        } catch {}
      }
    };
  }, [previewUrl]);

  // --- Edit message (client) ---
  const startEdit = (msg) => {
    setMenuOpenFor(null);
    setEditingMessageId(msg.id);
    setEditingText(msg.content === "This message was deleted" ? "" : msg.content || "");
  };

  const cancelEdit = () => {
    setEditingMessageId(null);
    setEditingText("");
  };

  const submitEdit = () => {
    const newText = editingText.trim();
    if (!newText) {
      return;
    }
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "edit", message_id: editingMessageId, content: newText }));
    } else {
      console.warn("WebSocket not open for edit");
    }
    cancelEdit();
  };

  // --- Delete message (client) ---
  const deleteMessage = (messageId) => {
    setMenuOpenFor(null);
    if (!messageId) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "delete", message_id: messageId }));
    } else {
      console.warn("WebSocket not open for delete");
    }
  };

  // --- Scroll ---
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    fetchConversation();
  }, [fetchConversation]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return {
    // state
    theme,
    users,
    selected,
    messages,
    text,
    typing,
    menuOpenFor,
    editingMessageId,
    editingText,
    // refs
    messagesEndRef,
    // attachment
    selectedFile,
    previewUrl,
    // setters/actions
    setSelected,
    setText,
    setMenuOpenFor,
    setEditingText,
    toggleTheme,
    // attachment handlers
    handleFileChange,
    removeAttachment,
    // helpers
    formatTimestamp,
    handleTyping,
    send,
    sendReaction,
    startEdit,
    cancelEdit,
    submitEdit,
    deleteMessage,
    fetchUsers,
    fetchConversation,
  };
}

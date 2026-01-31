// src/pages/Login.jsx
import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Link, useNavigate } from "react-router-dom";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(form);
      nav("/chat");
    } catch (errorMessage) {
      // errorMessage is a normalized string from AuthContext
      setErr(typeof errorMessage === "string" ? errorMessage : "Invalid username or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="welcome-container">
        <h1 className="welcome-title">Welcome to Chithi</h1>
        <p className="welcome-tagline">Your digital letter 💌</p>
      </div>

      <div style={{ maxWidth: 360, margin: "32px auto", textAlign: "center", fontSize: 20 }}>
        <h2>Login</h2>
        {err && <p style={{ color: "tomato", whiteSpace: "pre-wrap" }}>{err}</p>}
        <form onSubmit={submit}>
          <input
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            style={{ width: "100%", marginBottom: 8 }}
            autoComplete="username"
          />
          <input
            type="password"
            placeholder="Password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            style={{ width: "100%", marginBottom: 8 }}
            autoComplete="current-password"
          />
          <button type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p style={{ marginTop: 8 }}>
          Dont have an account yet? Go <Link to="/register">Signup</Link>
        </p>
      </div>
    </div>
  );
}

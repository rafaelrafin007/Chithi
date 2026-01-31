import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate, Link } from "react-router-dom";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    try {
      setErr("");
      await register(form);
      nav("/chat");
    } catch {
      setErr("Registration failed");
    }
  };

  return (
    <div style={{ maxWidth: 360, margin: "64px auto", textAlign: "center", fontSize: "20px" }}>
      <h2>Sign Up</h2>
      {err && <p style={{ color: "tomato" }}>{err}</p>}
      <form onSubmit={submit}>
        <input
          placeholder="Username"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          style={{ width: "100%", marginBottom: 8 }}
        />
        <input
          placeholder="Email (optional)"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          style={{ width: "100%", marginBottom: 8 }}
        />
        <input
          type="password"
          placeholder="Password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          style={{ width: "100%", marginBottom: 8 }}
        />
        <button type="submit">Create account</button>
      </form>
      <p style={{ marginTop: 8 }}>
        Have an account? Go <Link to="/login">Login</Link>
      </p>
    </div>
  );
}

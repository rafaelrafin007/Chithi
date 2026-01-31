import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user, booting } = useAuth();
  if (booting) return null; // no white flash; render nothing while booting
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

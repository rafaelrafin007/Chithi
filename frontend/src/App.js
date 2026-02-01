import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ChatPage from "./pages/ChatPage";
import Friends from "./pages/Friends";


export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/friends"
            element={
              <ProtectedRoute>
                <Friends />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

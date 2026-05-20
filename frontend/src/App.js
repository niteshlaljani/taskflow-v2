import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import AppShell from "@/components/AppShell";
import Board from "@/pages/Board";
import AppIndex from "@/pages/AppIndex";
import MyIssues from "@/pages/MyIssues";
import Projects from "@/pages/Projects";
import Settings from "@/pages/Settings";
import JoinInvite from "@/pages/JoinInvite";
import Sprints from "@/pages/Sprints";
import Views from "@/pages/Views";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-sm font-mono text-neutral-500">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AppRouter() {
  // Detect Emergent OAuth callback during render (prevents race conditions)
  const hash = typeof window !== "undefined" ? window.location.hash : "";
  if (hash && hash.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/join/:code" element={<JoinInvite />} />
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<AppIndex />} />
        <Route path="board/:projectId" element={<Board />} />
        <Route path="sprints/:projectId" element={<Sprints />} />
        <Route path="my-issues" element={<MyIssues />} />
        <Route path="projects" element={<Projects />} />
        <Route path="views" element={<Views />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </BrowserRouter>
  );
}

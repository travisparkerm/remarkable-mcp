import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getMe, setToken, clearToken, getRemarkableStatus, getRemarkableLibrary, type User } from "./lib/api";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Player from "./pages/Player";
import Settings from "./pages/Settings";
import Shows from "./pages/Shows";
import ShowDetail from "./pages/ShowDetail";
import ShowEditor from "./pages/ShowEditor";

function ProtectedRoute({
  user,
  children,
}: {
  user: User | null;
  children: React.ReactNode;
}) {
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // Check for token in URL (OAuth redirect)
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setToken(token);
      // Clean the URL
      window.history.replaceState({}, "", "/");
    }

    getMe()
      .then((u) => {
        setUser(u);
        // Prefetch reMarkable library in the background to warm the server cache
        getRemarkableStatus()
          .then((s) => { if (s.connected) getRemarkableLibrary(); })
          .catch(() => {}); // ignore prefetch errors
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = () => {
    clearToken();
    setUser(null);
    navigate("/login");
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-neutral-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute user={user}>
            <Dashboard user={user!} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/shows"
        element={
          <ProtectedRoute user={user}>
            <Shows user={user!} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/shows/new"
        element={
          <ProtectedRoute user={user}>
            <ShowEditor />
          </ProtectedRoute>
        }
      />
      <Route
        path="/shows/:showId/edit"
        element={
          <ProtectedRoute user={user}>
            <ShowEditor />
          </ProtectedRoute>
        }
      />
      <Route
        path="/shows/:showId"
        element={
          <ProtectedRoute user={user}>
            <ShowDetail />
          </ProtectedRoute>
        }
      />
      <Route
        path="/episode/:episodeId"
        element={
          <ProtectedRoute user={user}>
            <Player />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute user={user}>
            <Settings user={user!} />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

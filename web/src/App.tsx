import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getMe, type User } from "./lib/api";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Player from "./pages/Player";
import Settings from "./pages/Settings";

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
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = () => {
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
        path="/episode/:date"
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

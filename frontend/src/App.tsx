import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { ApiError, type User, fetchMe, login as apiLogin, logout as apiLogout } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { Dashboard } from "@/routes/Dashboard";
import { InvoiceDetail } from "@/routes/InvoiceDetail";
import { Login } from "@/routes/Login";
import { PublicInvoice } from "@/routes/PublicInvoice";
import { Settings } from "@/routes/Settings";

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const isPublicPage = location.pathname.startsWith("/p/");

  useEffect(() => {
    if (isPublicPage) {
      setBooting(false);
      return;
    }
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch((err: unknown) => {
        if (!cancelled && !(err instanceof ApiError && err.status === 401)) {
          console.error(err);
        }
      })
      .finally(() => {
        if (!cancelled) setBooting(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isPublicPage]);

  const handleLogin = useCallback(async (email: string, password: string) => {
    const me = await apiLogin(email, password);
    setUser(me);
  }, []);

  const handleLogout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    navigate("/login");
  }, [navigate]);

  if (booting && !isPublicPage) {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Loading Tagado…
      </main>
    );
  }

  return (
    <Routes>
      <Route path="/p/:token" element={<PublicInvoice />} />
      <Route
        path="/login"
        element={
          user ? (
            <Navigate to="/" replace />
          ) : (
            <Login login={handleLogin} onSuccess={() => navigate("/")} />
          )
        }
      />
      <Route
        path="/"
        element={
          user ? (
            <AppShell user={user} onLogout={() => void handleLogout()}>
              <Dashboard />
            </AppShell>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/invoices/:id"
        element={
          user ? (
            <AppShell user={user} onLogout={() => void handleLogout()}>
              <InvoiceDetail />
            </AppShell>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/settings"
        element={
          user ? (
            <AppShell user={user} onLogout={() => void handleLogout()}>
              <Settings />
            </AppShell>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to={user ? "/" : "/login"} replace />} />
    </Routes>
  );
}

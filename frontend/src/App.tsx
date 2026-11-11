import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { ApiError, type User, fetchMe, login as apiLogin, logout as apiLogout } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { Home } from "@/routes/Home";
import { InvoiceDetail } from "@/routes/InvoiceDetail";
import { Invoices } from "@/routes/Invoices";
import { Login } from "@/routes/Login";
import { PublicInvoice } from "@/routes/PublicInvoice";
import { Settings } from "@/routes/Settings";

function Protected({
  user,
  onLogout,
  children,
}: {
  user: User | null;
  onLogout: () => void;
  children: ReactNode;
}) {
  if (!user) return <Navigate to="/login" replace />;
  return (
    <AppShell user={user} onLogout={onLogout}>
      {children}
    </AppShell>
  );
}

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
          <Protected user={user} onLogout={() => void handleLogout()}>
            <Home />
          </Protected>
        }
      />
      <Route
        path="/invoices"
        element={
          <Protected user={user} onLogout={() => void handleLogout()}>
            <Invoices />
          </Protected>
        }
      />
      <Route
        path="/invoices/:id"
        element={
          <Protected user={user} onLogout={() => void handleLogout()}>
            <InvoiceDetail />
          </Protected>
        }
      />
      <Route path="/settings" element={<Navigate to="/settings/branding" replace />} />
      <Route path="/settings/business" element={<Navigate to="/settings/branding" replace />} />
      <Route
        path="/settings/:section"
        element={
          <Protected user={user} onLogout={() => void handleLogout()}>
            <Settings />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to={user ? "/" : "/login"} replace />} />
    </Routes>
  );
}

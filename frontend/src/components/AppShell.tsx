import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import type { User } from "@/api/client";

interface AppShellProps {
  user: User;
  onLogout: () => void;
  children: ReactNode;
}

export function AppShell({ user, onLogout, children }: AppShellProps) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-[var(--line)] bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link to="/" className="text-lg font-semibold tracking-tight text-[var(--ink)]">
            Tagado
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive ? "font-semibold text-[var(--accent)]" : "text-slate-600 hover:text-[var(--ink)]"
              }
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                isActive ? "font-semibold text-[var(--accent)]" : "text-slate-600 hover:text-[var(--ink)]"
              }
            >
              Settings
            </NavLink>
            <span className="hidden text-slate-400 sm:inline">{user.name}</span>
            <button
              type="button"
              onClick={onLogout}
              className="rounded-md border border-[var(--line)] px-3 py-1.5 text-slate-700 hover:bg-white"
            >
              Sign out
            </button>
          </nav>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</div>
    </div>
  );
}

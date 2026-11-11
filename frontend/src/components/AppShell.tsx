import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { type User, type WorkspaceSettings, fetchSettings } from "@/api/client";

interface AppShellProps {
  user: User;
  onLogout: () => void;
  children: ReactNode;
}

const NAV = [
  {
    group: "Workspace",
    items: [
      {
        to: "/",
        label: "Home",
        hint: "Enter your workspace",
        short: "Home",
        end: true,
      },
      {
        to: "/invoices",
        label: "Invoices",
        hint: "Track and follow up",
        short: "Inv",
        end: true,
      },
    ],
  },
  {
    group: "Settings",
    items: [
      {
        to: "/settings/branding",
        label: "Branding & identity",
        hint: "Business name, look, sender",
        short: "Brand",
      },
      {
        to: "/settings/payments",
        label: "Payment details",
        hint: "Bank, UPI, MSME",
        short: "Pay",
      },
      {
        to: "/settings/reminders",
        label: "Reminders",
        hint: "When follow-ups go out",
        short: "Time",
      },
      {
        to: "/settings/claude",
        label: "Connect Claude",
        hint: "Private connection link",
        short: "Claude",
      },
      {
        to: "/settings/users",
        label: "Users & roles",
        hint: "Who can act in this workspace",
        short: "Users",
      },
      {
        to: "/settings/data",
        label: "Data governance",
        hint: "Retention and access rules",
        short: "Data",
      },
    ],
  },
] as const;

export function AppShell({ user, onLogout, children }: AppShellProps) {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [workspace, setWorkspace] = useState<WorkspaceSettings | null>(null);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then((settings) => {
        if (cancelled) return;
        setWorkspace(settings);
        document.documentElement.style.setProperty("--accent", settings.accent_color || "#0f6e56");
        const existing = document.querySelector<HTMLLinkElement>("link[data-tagado-favicon]");
        if (settings.favicon_data_url) {
          const link = existing ?? document.createElement("link");
          link.rel = "icon";
          link.href = settings.favicon_data_url;
          link.dataset.tagadoFavicon = "true";
          if (!existing) document.head.appendChild(link);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [location.pathname.startsWith("/settings")]);

  const brandName = workspace?.business_name || "Tagado";
  const logo = workspace?.logo_data_url;

  return (
    <div className="min-h-screen lg:flex">
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[var(--line)] bg-[var(--sidebar)] text-[var(--ink)] transition-all duration-200 lg:static ${
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        } ${collapsed ? "lg:w-[92px]" : "w-[280px]"}`}
      >
        <div
          className={`flex items-center gap-3 border-b border-[var(--line)] px-4 py-4 ${
            collapsed ? "lg:justify-center" : ""
          }`}
        >
          <Link to="/" className="flex min-w-0 items-center gap-3">
            {logo ? (
              <img src={logo} alt="" className="h-10 w-10 shrink-0 rounded-xl object-contain" />
            ) : (
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-bold text-white shadow-sm">
                Tg
              </span>
            )}
            {!collapsed ? (
              <span className="min-w-0">
                <span className="block truncate text-base font-semibold tracking-tight">{brandName}</span>
                <span className="block truncate text-xs text-slate-500">Tagado workspace</span>
              </span>
            ) : null}
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {NAV.map((section) => (
            <div key={section.group} className="mb-5">
              {!collapsed ? (
                <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                  {section.group}
                </p>
              ) : null}
              <ul className="space-y-1">
                {section.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={"end" in item ? item.end : false}
                      title={item.label}
                      className={({ isActive }) =>
                        `block rounded-xl px-3 py-2.5 transition ${
                          isActive
                            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                            : "text-slate-600 hover:bg-white/70 hover:text-[var(--ink)]"
                        }`
                      }
                    >
                      <span
                        className={`block text-sm font-medium ${collapsed ? "text-center text-xs" : ""}`}
                      >
                        {collapsed ? item.short : item.label}
                      </span>
                      {!collapsed ? (
                        <span className="mt-0.5 block text-xs text-slate-500">{item.hint}</span>
                      ) : null}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-[var(--line)] p-3">
          {!collapsed ? (
            <div className="mb-3 rounded-xl bg-white/70 px-3 py-2">
              <p className="truncate text-sm font-medium">{user.name}</p>
              <p className="truncate text-xs text-slate-500">
                {user.email} · {user.role || "owner"}
              </p>
            </div>
          ) : null}
          <div className={`flex gap-2 ${collapsed ? "flex-col" : ""}`}>
            <button
              type="button"
              onClick={() => setCollapsed((value) => !value)}
              className="hidden flex-1 rounded-lg border border-[var(--line)] bg-white/80 px-3 py-2 text-xs font-medium lg:block"
            >
              {collapsed ? "»" : "Collapse"}
            </button>
            <button
              type="button"
              onClick={onLogout}
              className="flex-1 rounded-lg border border-[var(--line)] bg-white/80 px-3 py-2 text-xs font-medium"
            >
              {collapsed ? "Out" : "Sign out"}
            </button>
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-[var(--line)] bg-[var(--paper)]/90 px-4 py-3 backdrop-blur lg:hidden">
          <button
            type="button"
            className="rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm"
            onClick={() => setMobileOpen(true)}
          >
            Menu
          </button>
          <div>
            <p className="text-sm font-semibold">{brandName}</p>
            <p className="text-xs text-slate-500">Tagado workspace</p>
          </div>
        </div>
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</div>
      </div>
    </div>
  );
}

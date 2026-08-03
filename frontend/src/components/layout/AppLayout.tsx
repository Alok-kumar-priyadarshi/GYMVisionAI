/**
 * The authenticated application shell.
 *
 * Navigation is a single list rendered as a sidebar on wide screens and a
 * bottom bar on phones, so the labels and routes are declared once.
 */

import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/workout", label: "Workout", icon: "◆" },
  { to: "/exercises", label: "Exercises", icon: "◎" },
  { to: "/diet", label: "Diet", icon: "◍" },
  { to: "/progress", label: "Progress", icon: "▤" },
  { to: "/coach", label: "Coach", icon: "✦" },
  { to: "/profile", label: "Profile", icon: "◉" },
];

function navClasses(isActive: boolean): string {
  return [
    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-brand-50 text-brand-700" : "text-ink-muted hover:bg-surface-muted",
  ].join(" ");
}

export function AppLayout() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-dvh lg:flex">
      {/* Skip link: the first stop for keyboard and screen-reader users. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-3 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:shadow"
      >
        Skip to content
      </a>

      <aside className="hidden w-60 shrink-0 border-r border-line bg-white p-4 lg:flex lg:flex-col">
        <div className="px-3 py-2">
          <p className="text-lg font-semibold tracking-tight text-ink">GymVision</p>
          <p className="text-xs text-ink-muted">AI home trainer</p>
        </div>

        <nav aria-label="Main" className="mt-6 flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => navClasses(isActive)}
            >
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-line pt-4">
          <p className="truncate px-3 text-sm font-medium text-ink">{user?.name}</p>
          <p className="truncate px-3 text-xs text-ink-muted">{user?.email}</p>
          <Button
            variant="ghost"
            fullWidth
            className="mt-2"
            onClick={() => void signOut()}
          >
            Sign out
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line bg-white px-4 py-3 lg:hidden">
          <p className="font-semibold text-ink">GymVision</p>
          <Button variant="ghost" onClick={() => void signOut()}>
            Sign out
          </Button>
        </header>

        <main id="main" className="flex-1 px-4 py-6 pb-24 lg:px-8 lg:pb-8">
          <div className="mx-auto w-full max-w-5xl">
            <Outlet />
          </div>
        </main>

        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-6 border-t border-line bg-white lg:hidden"
        >
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                [
                  "flex flex-col items-center gap-0.5 py-2 text-[11px]",
                  isActive ? "text-brand-700" : "text-ink-muted",
                ].join(" ")
              }
            >
              <span aria-hidden="true" className="text-base">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}

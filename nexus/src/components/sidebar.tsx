"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ThemeSwitcher } from "./theme-switcher";

const NAV_ITEMS = [
  { href: "/", label: "STATUS" },
  { href: "/traces", label: "TRACES" },
  { href: "/memory", label: "MEMORY" },
  { href: "/graph", label: "GRAPH" },
  { href: "/chat", label: "CHAT" },
  { href: "/tasks", label: "TASKS" },
  { href: "/costs", label: "COSTS" },
  { href: "/activity", label: "ACTIVITY" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile top bar */}
      <div className="mobile-topbar">
        <button
          className="hamburger"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Menu"
        >
          {mobileOpen ? "\u2715" : "\u2630"}
        </button>
        <span className="mobile-brand">JARVIS</span>
        <ThemeSwitcher />
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="mobile-overlay"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — always visible on desktop, slide-in on mobile */}
      <nav className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h1>SYSTEM // ACTIVE</h1>
              <div className="brand-name">JARVIS</div>
            </div>
            <ThemeSwitcher />
          </div>
        </div>

        <div className="sidebar-nav">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link ${isActive ? "active" : ""}`}
                onClick={() => setMobileOpen(false)}
              >
                <span className="nav-dot" />
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="sidebar-footer">
          <div className="status-line">
            <span className="status-dot" />
            ENGRAM CLOUD SYNC
          </div>
        </div>
      </nav>
    </>
  );
}

"use client";
import { useState, useEffect, useRef } from "react";

const THEMES = [
  {
    id: "ember",
    label: "EMBER",
    desc: "Warm dark",
    colors: ["#1a0d0a", "#d4a046", "#e8dcc8", "#4a9e6a", "#c45a4a"],
  },
  {
    id: "arctic",
    label: "ARCTIC",
    desc: "Cool dark",
    colors: ["#0a1420", "#4a9ec8", "#d0dce8", "#4ac89a", "#c85a5a"],
  },
  {
    id: "terminal",
    label: "TERMINAL",
    desc: "Classic green",
    colors: ["#0a0a0a", "#33ff33", "#33ff33", "#33ff33", "#ff3333"],
  },
];

export function ThemeSwitcher() {
  const [theme, setTheme] = useState("ember");
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("jarvis-theme") || "ember";
    setTheme(saved);
    document.documentElement.setAttribute(
      "data-theme",
      saved === "ember" ? "" : saved
    );
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const switchTheme = (id: string) => {
    setTheme(id);
    localStorage.setItem("jarvis-theme", id);
    document.documentElement.setAttribute(
      "data-theme",
      id === "ember" ? "" : id
    );
    setOpen(false);
  };

  return (
    <div ref={panelRef} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        className="theme-toggle-btn"
        title="Theme settings"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
        </svg>
      </button>

      {open && (
        <div className="theme-panel">
          <div className="theme-panel-header">DISPLAY // THEME</div>
          {THEMES.map((t) => (
            <button
              key={t.id}
              onClick={() => switchTheme(t.id)}
              className={`theme-option ${theme === t.id ? "active" : ""}`}
            >
              <div className="theme-option-info">
                <span className="theme-option-name">{t.label}</span>
                <span className="theme-option-desc">{t.desc}</span>
              </div>
              <div className="theme-swatches">
                {t.colors.map((c, i) => (
                  <span
                    key={i}
                    className="theme-swatch"
                    style={{ background: c }}
                  />
                ))}
              </div>
              {theme === t.id && (
                <span className="theme-check">&#10003;</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

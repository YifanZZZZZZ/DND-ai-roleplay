import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import styles from "./AppShell.module.css";

export function AppShell() {
  const location = useLocation();
  const isPlayPage = location.pathname.endsWith("/play");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(
    () => window.localStorage.getItem("dnd-ai-sidebar-collapsed") === "true",
  );

  function toggleSidebar() {
    setIsSidebarCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("dnd-ai-sidebar-collapsed", String(next));
      return next;
    });
  }

  return (
    <div
      className={`${styles.shell} ${isSidebarCollapsed ? styles.shellCollapsed : ""}`}
    >
      <aside
        className={`${styles.sidebar} ${isSidebarCollapsed ? styles.sidebarCollapsed : ""}`}
      >
        <button
          aria-expanded={!isSidebarCollapsed}
          aria-label={isSidebarCollapsed ? "显示主导航" : "隐藏主导航"}
          className={styles.sidebarToggle}
          title={
            isSidebarCollapsed ? "显示战役和角色导航" : "隐藏战役和角色导航"
          }
          type="button"
          onClick={toggleSidebar}
        >
          {isSidebarCollapsed ? "☰" : "收起"}
        </button>
        {!isSidebarCollapsed && (
          <>
            <div className={styles.brand}>
              <span className={styles.brandMark}>D20</span>
              <div>
                <strong>DND AI</strong>
                <span>Roleplay Console</span>
              </div>
            </div>
            <nav className={styles.nav} aria-label="主导航">
              <NavLink
                className={({ isActive }) =>
                  isActive ? styles.active : undefined
                }
                to="/campaigns"
              >
                战役
              </NavLink>
              <NavLink
                className={({ isActive }) =>
                  isActive ? styles.active : undefined
                }
                to="/characters"
              >
                角色库
              </NavLink>
            </nav>
            <p className={styles.localOnly}>本地单人模式 · 无需登录</p>
          </>
        )}
      </aside>
      <main className={`${styles.main} ${isPlayPage ? styles.playMain : ""}`}>
        <Outlet />
      </main>
    </div>
  );
}

import { NavLink, Outlet } from "react-router-dom";

import styles from "./AppShell.module.css";

export function AppShell() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>D20</span>
          <div>
            <strong>DND AI</strong>
            <span>Roleplay Console</span>
          </div>
        </div>
        <nav className={styles.nav} aria-label="主导航">
          <NavLink
            className={({ isActive }) => (isActive ? styles.active : undefined)}
            to="/campaigns"
          >
            战役
          </NavLink>
          <NavLink
            className={({ isActive }) => (isActive ? styles.active : undefined)}
            to="/characters"
          >
            角色库
          </NavLink>
        </nav>
        <p className={styles.localOnly}>本地单人模式 · 无需登录</p>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}


import { Link } from "react-router-dom";

import styles from "./Page.module.css";

export function NotFoundPage() {
  return (
    <div className={styles.panel}>
      <span className={styles.eyebrow}>404</span>
      <h1>这里没有可探索的道路</h1>
      <Link className={styles.primary} to="/campaigns">
        返回战役列表
      </Link>
    </div>
  );
}


import type { ReactNode } from "react";

import styles from "./EmptyState.module.css";

interface EmptyStateProps {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ eyebrow, title, description, action }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <span>{eyebrow}</span>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}


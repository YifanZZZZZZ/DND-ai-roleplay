import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { createCampaign, listCampaigns } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { EmptyState } from "../components/EmptyState/EmptyState";
import styles from "./Page.module.css";

const statusLabels = {
  PREPARATION: "筹备中",
  ACTIVE: "进行中",
  PAUSED: "已暂停",
  COMPLETED: "已完成",
} as const;

export function CampaignsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [moduleOutline, setModuleOutline] = useState("");
  const campaigns = useQuery({ queryKey: queryKeys.campaigns, queryFn: listCampaigns });
  const createMutation = useMutation({
    mutationFn: createCampaign,
    onSuccess: async () => {
      setName("");
      setModuleOutline("");
      setShowForm(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.campaigns });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate({
      name: name.trim(),
      description: null,
      dmGuide: "",
      sceneNotes: "",
      moduleContent: moduleOutline.trim(),
      styleInstructions: "",
      openingInstructions: "",
      characterIds: [],
    });
  }

  return (
    <>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Campaign Archive</span>
          <h1>战役</h1>
          <p>筹备冒险、管理战役，并从原有的连续时间线继续跑团。</p>
        </div>
        <button className={styles.primary} onClick={() => setShowForm((value) => !value)}>
          {showForm ? "取消" : "创建战役"}
        </button>
      </header>

      {showForm && (
        <form className={`${styles.panel} ${styles.form}`} onSubmit={submit}>
          <label>
            战役名称
            <input
              required
              maxLength={160}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            模组大纲
            <textarea
              required
              maxLength={500_000}
              placeholder="写下主要背景、关键人物、冲突和可能的发展方向即可，其余内容交给 AI DM。"
              value={moduleOutline}
              onChange={(event) => setModuleOutline(event.target.value)}
            />
          </label>
          {createMutation.error && <p className={styles.error}>{createMutation.error.message}</p>}
          <div className={styles.formActions}>
            <button className={styles.primary} disabled={createMutation.isPending || !name.trim() || !moduleOutline.trim()}>
              {createMutation.isPending ? "创建中…" : "建立筹备战役"}
            </button>
          </div>
        </form>
      )}

      {campaigns.isLoading && <p>正在读取战役…</p>}
      {campaigns.error && <p className={styles.error}>{campaigns.error.message}</p>}
      {campaigns.data?.length === 0 && !showForm && (
        <EmptyState
          eyebrow="No campaign yet"
          title="第一段冒险还没有被写下"
          description="先创建一个筹备中的战役，再从全局角色库挑选这次参加冒险的角色。"
          action={
            <button className={styles.primary} onClick={() => setShowForm(true)}>
              创建第一个战役
            </button>
          }
        />
      )}
      {!!campaigns.data?.length && (
        <div className={styles.grid}>
          {campaigns.data.map((campaign) => (
            <Link className={styles.card} key={campaign.id} to={`/campaigns/${campaign.id}`}>
              <span className={styles.status}>{statusLabels[campaign.lifecycleStatus]}</span>
              <h2>{campaign.name}</h2>
              <p>{campaign.description || "尚未填写战役简介。"}</p>
              <div className={styles.meta}>
                <span>{campaign.memberCount} 名角色</span>
                <span>{campaign.hasRuntime ? "已有连续时间线" : "尚未启动"}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}

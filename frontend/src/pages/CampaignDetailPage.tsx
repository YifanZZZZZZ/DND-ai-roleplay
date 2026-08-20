import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  activateCampaign,
  completeCampaign,
  createSession,
  endSession,
  deleteCampaign,
  exportUrl,
  getCampaign,
  getSession,
  listCharacters,
  reopenCampaign,
  replaceCampaignMemberships,
  updateSessionHp,
  type SessionDetail,
} from "../api/client";
import { queryKeys } from "../api/queryKeys";
import styles from "./Page.module.css";

const statusLabels = {
  PREPARATION: "筹备中",
  ACTIVE: "进行中",
  COMPLETED: "已完成",
} as const;

type HpState = SessionDetail["hpStates"][number];

function HpEditor({ sessionId, hp }: { sessionId: string; hp: HpState }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(String(hp.currentHp));
  const mutation = useMutation({
    mutationFn: () => updateSessionHp(sessionId, hp.characterId, Number(value)),
    onSuccess: (data) => queryClient.setQueryData(queryKeys.session(sessionId), data),
  });
  const numericValue = Number(value);
  const isValid = Number.isInteger(numericValue) && numericValue >= 0 && numericValue <= hp.maxHp;

  return (
    <div className={styles.hpRow}>
      <span>{hp.name}</span>
      <input
        aria-label={`${hp.name} 当前 HP`}
        max={hp.maxHp}
        min={0}
        type="number"
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <button
        className={styles.secondary}
        disabled={!isValid || numericValue === hp.currentHp || mutation.isPending}
        onClick={() => mutation.mutate()}
        type="button"
      >
        保存 / {hp.maxHp}
      </button>
      {mutation.error && <p className={styles.error}>{mutation.error.message}</p>}
    </div>
  );
}

export function CampaignDetailPage() {
  const { campaignId } = useParams();
  const queryClient = useQueryClient();
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<string[]>([]);
  const [sessionTitle, setSessionTitle] = useState("");
  const campaign = useQuery({
    queryKey: queryKeys.campaign(campaignId ?? ""),
    queryFn: () => getCampaign(campaignId!),
    enabled: Boolean(campaignId),
  });
  const characters = useQuery({ queryKey: queryKeys.characters, queryFn: listCharacters });
  const activeSessionId = campaign.data?.activeSessionId ?? "";
  const activeSession = useQuery({
    queryKey: queryKeys.session(activeSessionId),
    queryFn: () => getSession(activeSessionId),
    enabled: Boolean(activeSessionId),
  });

  useEffect(() => {
    if (campaign.data) {
      setSelectedCharacterIds(campaign.data.members.map((member) => member.characterId));
    }
  }, [campaign.data]);

  async function refreshCampaign() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.campaign(campaignId ?? "") }),
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns }),
    ]);
  }

  const rosterMutation = useMutation({
    mutationFn: () =>
      replaceCampaignMemberships(
        campaignId!,
        campaign.data!.revision,
        selectedCharacterIds,
      ),
    onSuccess: refreshCampaign,
  });
  const activateMutation = useMutation({
    mutationFn: () => activateCampaign(campaignId!),
    onSuccess: refreshCampaign,
  });
  const completeMutation = useMutation({
    mutationFn: () => completeCampaign(campaignId!),
    onSuccess: refreshCampaign,
  });
  const reopenMutation = useMutation({
    mutationFn: () => reopenCampaign(campaignId!),
    onSuccess: refreshCampaign,
  });
  const createSessionMutation = useMutation({
    mutationFn: () => createSession(campaignId!, sessionTitle.trim()),
    onSuccess: async (data) => {
      setSessionTitle("");
      queryClient.setQueryData(queryKeys.session(data.id), data);
      await refreshCampaign();
    },
  });
  const endSessionMutation = useMutation({
    mutationFn: () => endSession(activeSessionId),
    onSuccess: async (data) => {
      queryClient.setQueryData(queryKeys.session(data.id), data);
      await refreshCampaign();
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteCampaign(campaignId!),
    onSuccess: () => { window.location.assign("/campaigns"); },
  });

  function toggleCharacter(characterId: string) {
    setSelectedCharacterIds((current) =>
      current.includes(characterId)
        ? current.filter((item) => item !== characterId)
        : [...current, characterId],
    );
  }

  function submitSession(event: FormEvent) {
    event.preventDefault();
    createSessionMutation.mutate();
  }

  if (campaign.isLoading) return <p>正在读取战役…</p>;
  if (campaign.error) return <p className={styles.error}>{campaign.error.message}</p>;
  if (!campaign.data) return null;

  const actionError =
    rosterMutation.error ??
    activateMutation.error ??
    completeMutation.error ??
    reopenMutation.error ??
    createSessionMutation.error ??
    endSessionMutation.error;
  const canActivate =
    campaign.data.members.length > 0 && campaign.data.members.every((member) => member.isConfigured);

  return (
    <>
      <Link className={styles.eyebrow} to="/campaigns">
        ← 返回战役列表
      </Link>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>{statusLabels[campaign.data.lifecycleStatus]}</span>
          <h1>{campaign.data.name}</h1>
          <p>{campaign.data.description || "尚未填写战役简介。"}</p>
        </div>
        <div className={styles.toolbar}>
          {campaign.data.lifecycleStatus === "PREPARATION" && (
            <button
              className={styles.primary}
              disabled={!canActivate || activateMutation.isPending}
              onClick={() => activateMutation.mutate()}
            >
              启动战役
            </button>
          )}
          {campaign.data.lifecycleStatus === "ACTIVE" && !activeSessionId && (
            <button
              className={styles.secondary}
              disabled={completeMutation.isPending}
              onClick={() => completeMutation.mutate()}
            >
              完成战役
            </button>
          )}
          {campaign.data.lifecycleStatus === "COMPLETED" && (
            <>
              <button className={styles.primary} disabled={reopenMutation.isPending} onClick={() => reopenMutation.mutate()}>重新开启</button>
              <button className={styles.secondary} disabled={deleteMutation.isPending} onClick={() => { if (window.confirm("永久删除战役及其消息、摘要和来源记忆？此操作不可恢复。")) deleteMutation.mutate(); }}>永久删除</button>
            </>
          )}
          <a className={styles.secondary} href={exportUrl("campaign", campaign.data.id)}>导出战役</a>
        </div>
      </header>

      <div className={styles.notice}>
        战役启动前，阵容内每名角色都需要 Roleplay Prompt 和已确认的 Excel 角色卡。
      </div>
      {actionError && <p className={styles.error}>{actionError.message}</p>}

      <h2 className={styles.sectionTitle}>冒险小队 · {campaign.data.memberCount}/6</h2>
      {campaign.data.lifecycleStatus === "PREPARATION" && (
        <div className={`${styles.panel} ${styles.form}`}>
          {characters.isLoading && <p>正在读取角色库…</p>}
          {characters.error && <p className={styles.error}>{characters.error.message}</p>}
          {characters.data?.length === 0 && (
            <p>
              角色库还是空的。<Link to="/characters">先创建角色</Link>。
            </p>
          )}
          {!!characters.data?.length && (
            <div className={styles.checklist}>
              {characters.data.map((character) => (
                <label className={styles.checkItem} key={character.id}>
                  <input
                    checked={selectedCharacterIds.includes(character.id)}
                    disabled={
                      !selectedCharacterIds.includes(character.id) && selectedCharacterIds.length >= 6
                    }
                    type="checkbox"
                    onChange={() => toggleCharacter(character.id)}
                  />
                  <span>{character.name}</span>
                  <small>{character.hasActiveSheet ? "角色卡就绪" : "角色卡缺失"}</small>
                </label>
              ))}
            </div>
          )}
          <div className={styles.formActions}>
            <button
              className={styles.secondary}
              disabled={rosterMutation.isPending}
              onClick={() => rosterMutation.mutate()}
              type="button"
            >
              {rosterMutation.isPending ? "保存中…" : "保存阵容"}
            </button>
          </div>
        </div>
      )}

      {campaign.data.members.length === 0 ? (
        <div className={styles.panel}>
          <p>尚未选择角色。</p>
        </div>
      ) : (
        <div className={styles.grid}>
          {campaign.data.members.map((member) => (
            <article className={styles.card} key={member.characterId}>
              <span className={styles.status}>{member.isConfigured ? "可参加" : "配置未完成"}</span>
              <h3>{member.name}</h3>
              <div className={styles.meta}>
                <span>最大 HP {member.maxHp}</span>
              </div>
            </article>
          ))}
        </div>
      )}

      <h2 className={styles.sectionTitle}>Sessions</h2>
      <div className={`${styles.panel} ${styles.stack}`}>
        {campaign.data.lifecycleStatus === "ACTIVE" && !activeSessionId && (
          <form className={styles.form} onSubmit={submitSession}>
            <label>
              新 Session 名称
              <input
                maxLength={160}
                placeholder="例如：Session 1 · 雾港来信"
                required
                value={sessionTitle}
                onChange={(event) => setSessionTitle(event.target.value)}
              />
            </label>
            <div className={styles.formActions}>
              <button
                className={styles.primary}
                disabled={!sessionTitle.trim() || createSessionMutation.isPending}
              >
                创建 Session
              </button>
            </div>
          </form>
        )}

        {activeSession.isLoading && <p>正在读取当前 Session…</p>}
        {activeSession.error && <p className={styles.error}>{activeSession.error.message}</p>}
        {activeSession.data?.status === "ACTIVE" && (
          <div className={styles.stack}>
            <div className={styles.toolbar}>
              <strong>{activeSession.data.title}</strong>
              <span className={styles.status}>进行中</span>
              <Link className={styles.secondary} to={`/sessions/${activeSession.data.id}`}>
                进入跑团
              </Link>
              <button
                className={styles.secondary}
                disabled={endSessionMutation.isPending}
                onClick={() => endSessionMutation.mutate()}
              >
                结束 Session
              </button>
            </div>
            {activeSession.data.hpStates.map((hp) => (
              <HpEditor
                hp={hp}
                key={`${hp.characterId}-${hp.currentHp}`}
                sessionId={activeSessionId}
              />
            ))}
          </div>
        )}

        {campaign.data.sessions.length === 0 && campaign.data.lifecycleStatus !== "ACTIVE" ? (
          <p>战役启动后，DM 可以在这里创建第一个 Session。</p>
        ) : (
          campaign.data.sessions.map((session) => (
            <div key={session.id}>
              <strong>{session.title}</strong> · {session.status === "ACTIVE" ? "进行中" : "已结束"}
            </div>
          ))
        )}
      </div>
    </>
  );
}

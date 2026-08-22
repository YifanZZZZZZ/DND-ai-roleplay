import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  correctMessageWithOoc,
  getSession,
  listMessages,
  retrySessionRuntime,
  sendDmMessage,
  stopSessionRuntime,
  updateSessionHp,
} from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useSessionEvents } from "../features/sessionEvents/useSessionEvents";
import styles from "./SessionPlayPage.module.css";

const runtimeLabels = {
  IDLE: "等待 DM",
  AGENTS_EVALUATING: "角色正在判断",
  VALIDATING_MESSAGE: "正在检查消息",
  WAITING_FOR_DM: "等待 DM 裁决",
  ERROR: "运行出错",
  ENDED: "Session 已结束",
} as const;

function HealthEditor({
  sessionId,
  characterId,
  name,
  currentHp,
  maxHp,
}: {
  sessionId: string;
  characterId: string;
  name: string;
  currentHp: number;
  maxHp: number;
}) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(String(currentHp));
  const saveMutation = useMutation({
    mutationFn: () => updateSessionHp(sessionId, characterId, Number(value)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId) });
    },
  });
  const numericValue = Number(value);
  const validValue = Number.isInteger(numericValue) && numericValue >= 0 && numericValue <= maxHp;
  const percent = Math.max(0, Math.min(100, (currentHp / maxHp) * 100));

  return (
    <section className={styles.partyMember}>
      <div className={styles.memberHeader}>
        <strong>{name}</strong>
        <span>
          {currentHp} / {maxHp}
        </span>
      </div>
      <div aria-label={`${name} HP`} className={styles.hpTrack}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className={styles.hpControl}>
        <input
          aria-label={`${name} 当前 HP`}
          max={maxHp}
          min={0}
          type="number"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <button
          disabled={!validValue || numericValue === currentHp || saveMutation.isPending}
          type="button"
          onClick={() => saveMutation.mutate()}
        >
          保存
        </button>
      </div>
    </section>
  );
}

export function SessionPlayPage() {
  const { sessionId } = useParams();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [recipientIds, setRecipientIds] = useState<string[]>([]);
  const [oocTargetId, setOocTargetId] = useState<string | null>(null);
  const [oocCorrection, setOocCorrection] = useState("");
  const [oocReplacement, setOocReplacement] = useState("");
  const session = useQuery({
    queryKey: queryKeys.session(sessionId ?? ""),
    queryFn: () => getSession(sessionId!),
    enabled: Boolean(sessionId),
  });
  const messages = useQuery({
    queryKey: queryKeys.messages(sessionId ?? ""),
    queryFn: () => listMessages(sessionId!),
    enabled: Boolean(sessionId),
  });
  useSessionEvents(sessionId);

  const sendMutation = useMutation({
    mutationFn: () =>
      sendDmMessage(sessionId!, {
        content: content.trim(),
        audience: isPrivate ? "PRIVATE" : "PUBLIC",
        recipientCharacterIds: isPrivate ? recipientIds : [],
        clientRequestId: crypto.randomUUID(),
      }),
    onSuccess: async () => {
      setContent("");
      setRecipientIds([]);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId!) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.messages(sessionId!) }),
      ]);
    },
  });
  const stopMutation = useMutation({
    mutationFn: () => stopSessionRuntime(sessionId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId!) });
    },
  });
  const retryMutation = useMutation({
    mutationFn: () => retrySessionRuntime(sessionId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId!) });
    },
  });
  const oocMutation = useMutation({
    mutationFn: () =>
      correctMessageWithOoc(sessionId!, {
        targetMessageId: oocTargetId!,
        correction: oocCorrection.trim(),
        replacementContent: oocReplacement.trim() || undefined,
        clientRequestId: crypto.randomUUID(),
      }),
    onSuccess: async () => {
      setOocTargetId(null);
      setOocCorrection("");
      setOocReplacement("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.session(sessionId!) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.messages(sessionId!) }),
      ]);
    },
  });

  function submitMessage(event: FormEvent) {
    event.preventDefault();
    if (content.trim()) sendMutation.mutate();
  }

  if (session.isLoading) return <p>正在恢复 Session…</p>;
  if (session.error) return <p className={styles.error}>{session.error.message}</p>;
  if (!session.data) return null;

  const isActive = session.data.status === "ACTIVE";
  const runtimeLabel = runtimeLabels[session.data.runtimeStatus];

  return (
    <div className={styles.playLayout}>
      <aside className={styles.partyPanel}>
        <Link className={styles.backLink} to={`/campaigns/${session.data.campaignId}`}>
          ← 返回战役
        </Link>
        <span className={styles.eyebrow}>Adventure Party</span>
        <h1>{session.data.title}</h1>
        <p>DM 可以在此维护精确 HP；Agent 只会获得定性健康状态。</p>
        <div className={styles.partyList}>
          {session.data.hpStates.map((hp) => (
            <HealthEditor
              characterId={hp.characterId}
              currentHp={hp.currentHp}
              key={`${hp.characterId}-${hp.currentHp}`}
              maxHp={hp.maxHp}
              name={hp.name}
              sessionId={session.data.id}
            />
          ))}
        </div>
      </aside>

      <main className={styles.chatPanel}>
        <header className={styles.runtimeHeader}>
          <div>
            <span className={styles.eyebrow}>Session Runtime</span>
            <h2>{runtimeLabel}</h2>
          </div>
          <button
            className={styles.stopButton}
            disabled={!isActive || session.data.runtimeStatus === "IDLE" || stopMutation.isPending}
            type="button"
            onClick={() => stopMutation.mutate()}
          >
            停止 AI 自动对话
          </button>
          {session.data.runtimeStatus === "ERROR" && isActive && (
            <button
              className={styles.secondary}
              disabled={retryMutation.isPending}
              onClick={() => retryMutation.mutate()}
              type="button"
            >
              {retryMutation.isPending ? "重试中…" : "重试最新事件"}
            </button>
          )}
        </header>

        {session.data.runtimeStatus === "ERROR" && session.data.lastErrorMessage && (
          <div className={styles.runtimeError} role="alert">
            <strong>{session.data.lastErrorCode || "RUNTIME_ERROR"}</strong>
            <span>{session.data.lastErrorMessage}</span>
          </div>
        )}
        {session.data.waitingRequest && (
          <div className={styles.waiting}>等待 DM：{session.data.waitingRequest}</div>
        )}
        <div className={styles.modelNotice}>DeepSeek 角色 Agent 已接入；可随时发送 DM 消息接管对话。</div>

        <section aria-label="消息时间线" className={styles.timeline}>
          {messages.isLoading && <p>正在读取消息…</p>}
          {messages.error && <p className={styles.error}>{messages.error.message}</p>}
          {messages.data?.length === 0 && (
            <div className={styles.emptyTimeline}>
              <strong>由 DM 写下第一段场景。</strong>
              <p>Session 开始后，角色会保持安静，直到收到第一条场内消息。</p>
            </div>
          )}
          {messages.data?.map((message) => (
            <article
              className={`${styles.message} ${message.senderType === "DM" ? styles.dmMessage : styles.characterMessage}`}
              key={message.id}
            >
              <div className={styles.messageMeta}>
                <strong>{message.senderType === "DM" ? "DM" : message.senderName}</strong>
                {message.audience === "PRIVATE" && (
                  <span>私密 · {message.recipients.map((recipient) => recipient.name).join("、")}</span>
                )}
                {message.isOocCorrected && <span>已 OOC 纠正</span>}
              </div>
              <p>{message.content}</p>
              {message.isOocCorrected && message.oocCorrectionNote && (
                <small className={styles.oocNote}>OOC：{message.oocCorrectionNote}</small>
              )}
              {isActive && (
                <button
                  className={styles.oocButton}
                  type="button"
                  onClick={() => setOocTargetId(message.id)}
                >
                  OOC 纠正
                </button>
              )}
            </article>
          ))}
        </section>

        {oocTargetId && (
          <form
            className={styles.oocForm}
            onSubmit={(event) => {
              event.preventDefault();
              if (oocCorrection.trim()) oocMutation.mutate();
            }}
          >
            <strong>OOC 纠正</strong>
            <textarea
              maxLength={3000}
              placeholder="说明哪里有误，以及角色应如何重新理解这件事…"
              value={oocCorrection}
              onChange={(event) => setOocCorrection(event.target.value)}
            />
            <textarea
              maxLength={3000}
              placeholder="若纠正的是 DM 消息，请填写正确的替代正文；纠正角色消息可留空。"
              value={oocReplacement}
              onChange={(event) => setOocReplacement(event.target.value)}
            />
            {oocMutation.error && <p className={styles.error}>{oocMutation.error.message}</p>}
            <div className={styles.composerActions}>
              <button type="button" onClick={() => setOocTargetId(null)}>
                取消
              </button>
              <button disabled={!oocCorrection.trim() || oocMutation.isPending}>
                {oocMutation.isPending ? "纠正中…" : "提交 OOC"}
              </button>
            </div>
          </form>
        )}

        <form className={styles.composer} onSubmit={submitMessage}>
          <label>
            DM 场内消息
            <textarea
              disabled={!isActive || sendMutation.isPending}
              maxLength={3000}
              placeholder="描述场景、NPC 发言、裁决结果或新的世界事实…"
              value={content}
              onChange={(event) => setContent(event.target.value)}
            />
          </label>
          <label className={styles.privateToggle}>
            <input checked={isPrivate} type="checkbox" onChange={(event) => setIsPrivate(event.target.checked)} />
            私密发送给指定角色
          </label>
          {isPrivate && <div className={styles.recipientList}>
            {session.data.hpStates.map((hp) => <label key={hp.characterId}>
              <input checked={recipientIds.includes(hp.characterId)} type="checkbox" onChange={() => setRecipientIds((current) => current.includes(hp.characterId) ? current.filter((id) => id !== hp.characterId) : [...current, hp.characterId])} />
              {hp.name}
            </label>)}
          </div>}
          {sendMutation.error && <p className={styles.error}>{sendMutation.error.message}</p>}
          <div className={styles.composerActions}>
            <span>{content.length}/3000</span>
            <button disabled={!isActive || !content.trim() || (isPrivate && recipientIds.length === 0) || sendMutation.isPending}>
              {sendMutation.isPending ? "发送中…" : "发送场内消息"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

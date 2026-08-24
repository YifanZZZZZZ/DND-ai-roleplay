import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  adjudicateSkillCheck,
  createSkillCheck,
  createDmDraft,
  discardDmDraft,
  correctMessageWithOoc,
  getCampaignPlayState,
  listCampaignSkills,
  listMessages,
  listDmDrafts,
  listSkillChecks,
  publishDmDraft,
  retryCampaignRuntime,
  sendDmMessage,
  stopCampaignRuntime,
  updateCampaignHp,
  updateDmDraft,
} from "../api/client";
import type {
  CampaignPlayState,
  DmDraftView,
  RollMode,
  SkillName,
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
  ENDED: "Campaign 已完成",
} as const;

const skillLabels: Record<SkillName, string> = {
  athletics: "运动",
  acrobatics: "体操",
  sleight_of_hand: "巧手",
  stealth: "隐匿",
  arcana: "奥秘",
  history: "历史",
  investigation: "调查",
  nature: "自然",
  religion: "宗教",
  animal_handling: "驯兽",
  insight: "洞悉",
  medicine: "医药",
  perception: "感知",
  survival: "求生",
  deception: "欺瞒",
  intimidation: "威吓",
  performance: "表演",
  persuasion: "游说",
};

const skillNames = Object.keys(skillLabels) as SkillName[];

function DicePanel({
  campaignId,
  active,
}: {
  campaignId: string;
  active: boolean;
}) {
  const queryClient = useQueryClient();
  const [characterId, setCharacterId] = useState("");
  const [skill, setSkill] = useState<SkillName>("perception");
  const [rollMode, setRollMode] = useState<RollMode>("NORMAL");
  const [dc, setDc] = useState("");
  const [reason, setReason] = useState("");
  const members = useQuery({
    queryKey: queryKeys.campaignSkills(campaignId),
    queryFn: () => listCampaignSkills(campaignId),
  });
  const checks = useQuery({
    queryKey: queryKeys.skillChecks(campaignId),
    queryFn: () => listSkillChecks(campaignId),
  });
  const rollMutation = useMutation({
    mutationFn: () =>
      createSkillCheck(campaignId, {
        characterId,
        skill,
        rollMode,
        dc: dc.trim() ? Number(dc) : undefined,
        reason: reason.trim() || undefined,
        clientRequestId: crypto.randomUUID(),
      }),
    onSuccess: async () => {
      setReason("");
      setDc("");
      await queryClient.invalidateQueries({
        queryKey: queryKeys.skillChecks(campaignId),
      });
    },
  });
  const adjudicateMutation = useMutation({
    mutationFn: ({
      checkId,
      outcome,
    }: {
      checkId: string;
      outcome: "SUCCESS" | "FAILURE" | "PARTIAL_SUCCESS";
    }) => adjudicateSkillCheck(checkId, outcome),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.skillChecks(campaignId),
      });
    },
  });
  const selectedMember = members.data?.find(
    (member) => member.characterId === characterId,
  );

  return (
    <section className={styles.dicePanel}>
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>Dice Desk</span>
          <h2>D20 检定</h2>
        </div>
        <span className={styles.confirmHint}>每次投掷都由 DM 确认</span>
      </div>
      <div className={styles.diceForm}>
        <label>
          角色
          <select
            value={characterId}
            onChange={(event) => setCharacterId(event.target.value)}
          >
            <option value="">选择角色</option>
            {members.data?.map((member) => (
              <option key={member.characterId} value={member.characterId}>
                {member.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          技能
          <select
            value={skill}
            onChange={(event) => setSkill(event.target.value as SkillName)}
          >
            {skillNames.map((name) => (
              <option key={name} value={name}>
                {skillLabels[name]} ({name})
              </option>
            ))}
          </select>
        </label>
        <label>
          模式
          <select
            value={rollMode}
            onChange={(event) => setRollMode(event.target.value as RollMode)}
          >
            <option value="NORMAL">普通</option>
            <option value="ADVANTAGE">优势</option>
            <option value="DISADVANTAGE">劣势</option>
          </select>
        </label>
        <label>
          DC（可选）
          <input
            min={0}
            max={1000}
            type="number"
            value={dc}
            onChange={(event) => setDc(event.target.value)}
          />
        </label>
        <label className={styles.wideField}>
          原因 / 场景提示
          <input
            maxLength={300}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="例如：察觉门后的动静"
          />
        </label>
      </div>
      <div className={styles.rollActions}>
        <span>
          {selectedMember
            ? `${selectedMember.name} · ${skillLabels[skill]} 加值 ${(selectedMember.modifiers[skill] ?? 0) >= 0 ? "+" : ""}${selectedMember.modifiers[skill] ?? 0}`
            : "先选择角色"}
        </span>
        <button
          disabled={!active || !characterId || rollMutation.isPending}
          type="button"
          onClick={() => rollMutation.mutate()}
        >
          {rollMutation.isPending ? "投掷中…" : "确认并投掷 D20"}
        </button>
      </div>
      {rollMutation.error && (
        <p className={styles.error}>{rollMutation.error.message}</p>
      )}
      <div className={styles.checkHistory}>
        {checks.data?.slice(0, 8).map((check) => (
          <article className={styles.checkCard} key={check.id}>
            <div>
              <strong>
                {check.characterName} · {skillLabels[check.skill]}
              </strong>
              <span>
                {check.rollMode === "NORMAL"
                  ? "普通"
                  : check.rollMode === "ADVANTAGE"
                    ? "优势"
                    : "劣势"}
              </span>
            </div>
            <p>
              D20 {check.dieOne}
              {check.dieTwo === null ? "" : ` / ${check.dieTwo}`} → 取{" "}
              {check.selectedDie}，加值 {check.modifierSnapshot >= 0 ? "+" : ""}
              {check.modifierSnapshot} = <strong>{check.total}</strong>
              {check.dc === null ? "" : ` · DC ${check.dc}`}
            </p>
            <small>
              {check.systemOutcome === "UNRESOLVED"
                ? "等待 DM 裁决"
                : check.systemOutcome === "PASS"
                  ? "系统通过"
                  : "系统失败"}
              {check.dmAdjudication
                ? ` · DM：${check.dmAdjudication === "SUCCESS" ? "成功" : check.dmAdjudication === "FAILURE" ? "失败" : "部分成功"}`
                : ""}
            </small>
            {check.systemOutcome === "UNRESOLVED" &&
              check.status === "VALID" && (
                <div className={styles.adjudicationActions}>
                  <button
                    type="button"
                    onClick={() =>
                      adjudicateMutation.mutate({
                        checkId: check.id,
                        outcome: "SUCCESS",
                      })
                    }
                  >
                    成功
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      adjudicateMutation.mutate({
                        checkId: check.id,
                        outcome: "FAILURE",
                      })
                    }
                  >
                    失败
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      adjudicateMutation.mutate({
                        checkId: check.id,
                        outcome: "PARTIAL_SUCCESS",
                      })
                    }
                  >
                    部分成功
                  </button>
                </div>
              )}
          </article>
        ))}
      </div>
    </section>
  );
}

function DmDraftPanel({
  campaignId,
  active,
  characters,
  onPublished,
}: {
  campaignId: string;
  active: boolean;
  characters: CampaignPlayState["hpStates"];
  onPublished: () => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState<DmDraftView | null>(null);
  const drafts = useQuery({
    queryKey: queryKeys.dmDrafts(campaignId),
    queryFn: () => listDmDrafts(campaignId),
  });
  const [assistMode, setAssistMode] = useState<"POLISH" | "EXPAND" | "REWRITE">(
    "EXPAND",
  );
  // Kept after generating so "重新生成" can re-run the same rough draft.
  const [lastPrompt, setLastPrompt] = useState("");
  const createMutation = useMutation({
    mutationFn: (source: string) =>
      createDmDraft(campaignId, { prompt: source.trim(), assistMode }),
    onSuccess: async (value) => {
      setDraft(value);
      setPrompt("");
      await drafts.refetch();
    },
  });
  const regenerateMutation = useMutation({
    mutationFn: async () => {
      if (draft) await discardDmDraft(draft.id);
      return createDmDraft(campaignId, {
        prompt: lastPrompt.trim(),
        assistMode,
      });
    },
    onSuccess: async (value) => {
      setDraft(value);
      await drafts.refetch();
    },
  });
  const updateMutation = useMutation({
    mutationFn: () =>
      updateDmDraft(draft!.id, {
        revision: draft!.revision,
        content: editedContent.trim(),
        audience: isPrivate ? "PRIVATE" : "PUBLIC",
        recipientCharacterIds: isPrivate ? recipientIds : [],
      }),
    onSuccess: async (value) => {
      setDraft(value);
      await drafts.refetch();
    },
  });
  const publishMutation = useMutation({
    mutationFn: () => publishDmDraft(draft!.id),
    onSuccess: async () => {
      setDraft(null);
      await drafts.refetch();
      onPublished();
    },
  });
  const [editedContent, setEditedContent] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [recipientIds, setRecipientIds] = useState<string[]>([]);
  const discardMutation = useMutation({
    mutationFn: () => discardDmDraft(draft!.id),
    onSuccess: async () => {
      setDraft(null);
      await drafts.refetch();
    },
  });

  useEffect(() => {
    setEditedContent(draft?.content ?? "");
    setIsPrivate(draft?.audience === "PRIVATE");
    setRecipientIds(draft?.recipientCharacterIds ?? []);
  }, [draft]);
  useEffect(() => {
    if (!drafts.data) return;
    const newest =
      drafts.data.find((item) => ["READY", "DRAFT"].includes(item.status)) ??
      null;
    setDraft((current) => {
      if (!current) return newest;
      const currentServer = drafts.data?.find((item) => item.id === current.id);
      if (!currentServer || !["READY", "DRAFT"].includes(currentServer.status))
        return newest;
      if (
        newest &&
        newest.id !== current.id &&
        newest.createdAt > currentServer.createdAt
      )
        return newest;
      return currentServer;
    });
  }, [drafts.data]);
  const visibilityChanged =
    Boolean(draft) &&
    (isPrivate !== (draft!.audience === "PRIVATE") ||
      JSON.stringify([...recipientIds].sort()) !==
        JSON.stringify([...draft!.recipientCharacterIds].sort()));
  const isDirty =
    Boolean(draft) && (editedContent !== draft!.content || visibilityChanged);

  return (
    <section className={styles.draftPanel}>
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>AI DM Desk</span>
          <h2>叙事草稿</h2>
        </div>
        <span className={styles.confirmHint}>AI 不会自动发送</span>
      </div>
      {!draft && (
        <>
          <textarea
            disabled={!active || createMutation.isPending}
            maxLength={6000}
            placeholder="用最简单的话写你想回什么，AI 会补上氛围和 NPC 语气。例：守卫拦住他们，问来干嘛，态度不好"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <div className={styles.assistModes}>
            {(
              [
                ["POLISH", "只改文笔"],
                ["EXPAND", "扩写细节"],
                ["REWRITE", "重写结构"],
              ] as const
            ).map(([value, label]) => (
              <label key={value}>
                <input
                  checked={assistMode === value}
                  name="assist-mode"
                  type="radio"
                  onChange={() => setAssistMode(value)}
                />
                {label}
              </label>
            ))}
          </div>
          {createMutation.error && (
            <p className={styles.error}>{createMutation.error.message}</p>
          )}
          <button
            className={styles.draftButton}
            disabled={!active || !prompt.trim() || createMutation.isPending}
            type="button"
            onClick={() => {
              setLastPrompt(prompt);
              createMutation.mutate(prompt);
            }}
          >
            {createMutation.isPending ? "生成中…" : "生成 AI DM 草稿"}
          </button>
        </>
      )}
      {draft && (
        <>
          <div className={styles.draftStatus}>
            草稿待确认 · 可编辑 · revision {draft.revision}
          </div>
          <textarea
            maxLength={1200}
            value={editedContent}
            onChange={(event) => setEditedContent(event.target.value)}
          />
          {draft.improvisedNotes.length > 0 && (
            <div className={styles.improvised}>
              <strong>AI 自己加的内容</strong>
              <ul>
                {draft.improvisedNotes.map((note, index) => (
                  <li key={index}>{note}</li>
                ))}
              </ul>
            </div>
          )}
          <label className={styles.privateToggle}>
            <input
              checked={isPrivate}
              type="checkbox"
              onChange={(event) => setIsPrivate(event.target.checked)}
            />
            私密发送给指定角色
          </label>
          {isPrivate && (
            <div className={styles.recipientList}>
              {characters.map((character) => (
                <label key={character.characterId}>
                  <input
                    checked={recipientIds.includes(character.characterId)}
                    type="checkbox"
                    onChange={() =>
                      setRecipientIds((current) =>
                        current.includes(character.characterId)
                          ? current.filter((id) => id !== character.characterId)
                          : [...current, character.characterId],
                      )
                    }
                  />
                  {character.name}
                </label>
              ))}
            </div>
          )}
          {(updateMutation.error ||
            publishMutation.error ||
            discardMutation.error) && (
            <p className={styles.error}>
              {
                (
                  updateMutation.error ??
                  publishMutation.error ??
                  discardMutation.error
                )?.message
              }
            </p>
          )}
          <div className={styles.draftActions}>
            <button
              disabled={
                !editedContent.trim() ||
                (isPrivate && recipientIds.length === 0) ||
                updateMutation.isPending ||
                !isDirty
              }
              type="button"
              onClick={() => updateMutation.mutate()}
            >
              保存编辑
            </button>
            <button
              className={styles.draftButton}
              disabled={
                !editedContent.trim() ||
                isDirty ||
                publishMutation.isPending ||
                updateMutation.isPending
              }
              type="button"
              onClick={() => publishMutation.mutate()}
            >
              {isPrivate ? "确认并私密发送" : "确认并公开发送"}
            </button>
            {lastPrompt.trim() && (
              <button
                disabled={
                  regenerateMutation.isPending || publishMutation.isPending
                }
                type="button"
                onClick={() => regenerateMutation.mutate()}
              >
                {regenerateMutation.isPending ? "重新生成中…" : "重新生成"}
              </button>
            )}
            <button
              disabled={
                discardMutation.isPending ||
                updateMutation.isPending ||
                publishMutation.isPending
              }
              type="button"
              onClick={() => discardMutation.mutate()}
            >
              丢弃草稿
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function HealthEditor({
  campaignId,
  characterId,
  name,
  currentHp,
  maxHp,
}: {
  campaignId: string;
  characterId: string;
  name: string;
  currentHp: number;
  maxHp: number;
}) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(String(currentHp));
  const saveMutation = useMutation({
    mutationFn: () => updateCampaignHp(campaignId, characterId, Number(value)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.play(campaignId),
      });
    },
  });
  const numericValue = Number(value);
  const validValue =
    Number.isInteger(numericValue) &&
    numericValue >= 0 &&
    numericValue <= maxHp;
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
          disabled={
            !validValue || numericValue === currentHp || saveMutation.isPending
          }
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
  const { campaignId } = useParams();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [recipientIds, setRecipientIds] = useState<string[]>([]);
  const [addressedIds, setAddressedIds] = useState<string[]>([]);
  const [oocTargetId, setOocTargetId] = useState<string | null>(null);
  const [oocCorrection, setOocCorrection] = useState("");
  const [oocReplacement, setOocReplacement] = useState("");
  const conversationScrollRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const play = useQuery({
    queryKey: queryKeys.play(campaignId ?? ""),
    queryFn: () => getCampaignPlayState(campaignId!),
    enabled: Boolean(campaignId),
  });
  const messages = useQuery({
    queryKey: queryKeys.messages(campaignId ?? ""),
    queryFn: () => listMessages(campaignId!),
    enabled: Boolean(campaignId),
  });
  useSessionEvents(campaignId);
  const latestMessageId = messages.data?.at(-1)?.id;

  useEffect(() => {
    if (!latestMessageId || !shouldAutoScrollRef.current) return;
    const frame = window.requestAnimationFrame(() => {
      const container = conversationScrollRef.current;
      if (container)
        container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [latestMessageId]);

  // A character who cannot see the message cannot be addressed by it, so the
  // selection is intersected with the current visibility before it is sent.
  const visibleRecipientIds = isPrivate
    ? recipientIds
    : (play.data?.hpStates ?? []).map((hp) => hp.characterId);
  const visibleAddressedIds = addressedIds.filter((id) =>
    visibleRecipientIds.includes(id),
  );

  const sendMutation = useMutation({
    mutationFn: () =>
      sendDmMessage(campaignId!, {
        content: content.trim(),
        audience: isPrivate ? "PRIVATE" : "PUBLIC",
        recipientCharacterIds: isPrivate ? recipientIds : [],
        addressedCharacterIds: visibleAddressedIds,
        clientRequestId: crypto.randomUUID(),
      }),
    onSuccess: async () => {
      setContent("");
      setRecipientIds([]);
      setAddressedIds([]);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.play(campaignId!),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.messages(campaignId!),
        }),
      ]);
    },
  });
  const stopMutation = useMutation({
    mutationFn: () => stopCampaignRuntime(campaignId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.play(campaignId!),
      });
    },
  });
  const retryMutation = useMutation({
    mutationFn: () => retryCampaignRuntime(campaignId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.play(campaignId!),
      });
    },
  });
  const oocMutation = useMutation({
    mutationFn: () =>
      correctMessageWithOoc(campaignId!, {
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
        queryClient.invalidateQueries({
          queryKey: queryKeys.play(campaignId!),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.messages(campaignId!),
        }),
      ]);
    },
  });

  function submitMessage(event: FormEvent) {
    event.preventDefault();
    if (content.trim()) sendMutation.mutate();
  }

  if (play.isLoading) return <p>正在恢复 Campaign…</p>;
  if (play.error) return <p className={styles.error}>{play.error.message}</p>;
  if (!play.data) return null;

  const isActive = play.data.lifecycleStatus === "ACTIVE";
  const runtimeLabel = runtimeLabels[play.data.runtimeStatus];

  return (
    <div className={styles.playLayout}>
      <aside className={styles.partyPanel}>
        <Link
          className={styles.backLink}
          to={`/campaigns/${play.data.campaignId}`}
        >
          ← 返回战役
        </Link>
        <span className={styles.eyebrow}>Adventure Party</span>
        <h1>Campaign 跑团</h1>
        <p>DM 可以在此维护精确 HP；Agent 只会获得定性健康状态。</p>
        <div className={styles.partyList}>
          {play.data.hpStates.map((hp) => (
            <HealthEditor
              characterId={hp.characterId}
              currentHp={hp.currentHp}
              key={`${hp.characterId}-${hp.currentHp}`}
              maxHp={hp.maxHp}
              name={hp.name}
              campaignId={play.data.campaignId}
            />
          ))}
        </div>
        {campaignId && (
          <DicePanel
            active={play.data?.lifecycleStatus === "ACTIVE"}
            campaignId={campaignId}
          />
        )}
      </aside>

      <main className={styles.chatPanel}>
        <header className={styles.runtimeHeader}>
          <div>
            <span className={styles.eyebrow}>Campaign Runtime</span>
            <h2>{runtimeLabel}</h2>
          </div>
          <button
            className={styles.stopButton}
            disabled={
              !isActive ||
              play.data.runtimeStatus === "IDLE" ||
              stopMutation.isPending
            }
            type="button"
            onClick={() => stopMutation.mutate()}
          >
            停止 AI 自动对话
          </button>
          {play.data.runtimeStatus === "ERROR" && isActive && (
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

        <div
          className={styles.conversationScroll}
          ref={conversationScrollRef}
          onScroll={(event) => {
            const element = event.currentTarget;
            shouldAutoScrollRef.current =
              element.scrollHeight - element.scrollTop - element.clientHeight <
              96;
          }}
        >
          {play.data.runtimeStatus === "ERROR" &&
            play.data.lastErrorMessage && (
              <div className={styles.runtimeError} role="alert">
                <strong>{play.data.lastErrorCode || "RUNTIME_ERROR"}</strong>
                <span>{play.data.lastErrorMessage}</span>
              </div>
            )}
          {play.data.runtimeStatus !== "ERROR" &&
            play.data.lastErrorCode === "CHARACTER_MESSAGE_REJECTED" &&
            play.data.lastErrorMessage && (
              <div className={styles.runtimeWarning} role="status">
                <strong>候选被发布前检查拦下</strong>
                <span>{play.data.lastErrorMessage}</span>
              </div>
            )}
          {play.data.waitingRequest && (
            <div className={styles.waiting}>
              等待 DM：{play.data.waitingRequest}
            </div>
          )}
          <div className={styles.modelNotice}>
            DeepSeek 角色 Agent 已接入；可随时发送 DM 消息接管对话。
          </div>

          <section aria-label="消息时间线" className={styles.timeline}>
            {messages.isLoading && <p>正在读取消息…</p>}
            {messages.error && (
              <p className={styles.error}>{messages.error.message}</p>
            )}
            {messages.data?.length === 0 && (
              <div className={styles.emptyTimeline}>
                <strong>由 DM 写下第一段场景。</strong>
                <p>Campaign 启动后，角色会保持安静，直到收到第一条场内消息。</p>
              </div>
            )}
            {messages.data?.map((message) => (
              <article
                className={`${styles.message} ${message.senderType === "DM" ? styles.dmMessage : styles.characterMessage}`}
                key={message.id}
              >
                <div className={styles.messageMeta}>
                  <strong>
                    {message.senderType === "DM" ? "DM" : message.senderName}
                  </strong>
                  {message.audience === "PRIVATE" && (
                    <span>
                      私密 ·{" "}
                      {message.recipients
                        .map((recipient) => recipient.name)
                        .join("、")}
                    </span>
                  )}
                  {message.isOocCorrected && <span>已 OOC 纠正</span>}
                </div>
                <p>{message.content}</p>
                {message.isOocCorrected && message.oocCorrectionNote && (
                  <small className={styles.oocNote}>
                    OOC：{message.oocCorrectionNote}
                  </small>
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

          {campaignId && (
            <DmDraftPanel
              active={isActive}
              campaignId={campaignId}
              characters={play.data.hpStates}
              onPublished={() =>
                queryClient.invalidateQueries({
                  queryKey: queryKeys.messages(campaignId),
                })
              }
            />
          )}

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
              {oocMutation.error && (
                <p className={styles.error}>{oocMutation.error.message}</p>
              )}
              <div className={styles.composerActions}>
                <button type="button" onClick={() => setOocTargetId(null)}>
                  取消
                </button>
                <button
                  disabled={!oocCorrection.trim() || oocMutation.isPending}
                >
                  {oocMutation.isPending ? "纠正中…" : "提交 OOC"}
                </button>
              </div>
            </form>
          )}
        </div>

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
            <input
              checked={isPrivate}
              type="checkbox"
              onChange={(event) => setIsPrivate(event.target.checked)}
            />
            私密发送给指定角色
          </label>
          {isPrivate && (
            <div className={styles.recipientList}>
              {play.data.hpStates.map((hp) => (
                <label key={hp.characterId}>
                  <input
                    checked={recipientIds.includes(hp.characterId)}
                    type="checkbox"
                    onChange={() =>
                      setRecipientIds((current) =>
                        current.includes(hp.characterId)
                          ? current.filter((id) => id !== hp.characterId)
                          : [...current, hp.characterId],
                      )
                    }
                  />
                  {hp.name}
                </label>
              ))}
            </div>
          )}
          <div className={styles.addressing}>
            <span className={styles.addressingLabel}>
              这句话说给谁听（可选）
              <em>
                勾选后这些角色优先回应。用「你们两个」这类代词点名时尤其需要。
              </em>
            </span>
            <div className={styles.recipientList}>
              {play.data.hpStates
                .filter((hp) => visibleRecipientIds.includes(hp.characterId))
                .map((hp) => (
                  <label key={hp.characterId}>
                    <input
                      checked={addressedIds.includes(hp.characterId)}
                      type="checkbox"
                      onChange={() =>
                        setAddressedIds((current) =>
                          current.includes(hp.characterId)
                            ? current.filter((id) => id !== hp.characterId)
                            : [...current, hp.characterId],
                        )
                      }
                    />
                    {hp.name}
                  </label>
                ))}
            </div>
          </div>
          {sendMutation.error && (
            <p className={styles.error}>{sendMutation.error.message}</p>
          )}
          <div className={styles.composerActions}>
            <span>{content.length}/3000</span>
            <button
              disabled={
                !isActive ||
                !content.trim() ||
                (isPrivate && recipientIds.length === 0) ||
                sendMutation.isPending
              }
            >
              {sendMutation.isPending ? "发送中…" : "发送场内消息"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

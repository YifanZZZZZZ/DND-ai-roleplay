import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  activateCampaign,
  completeCampaign,
  deleteCampaign,
  exportUrl,
  generateOpeningDraft,
  getCampaign,
  getCampaignPlayState,
  listCharacters,
  listCampaignAcquaintances,
  listDmDrafts,
  listNpcs,
  extractNpcs,
  updateNpc,
  deleteNpc,
  pauseCampaign,
  replaceCampaignMemberships,
  resumeCampaign,
  updateCampaignHp,
  updateCampaign,
  publishDmDraft,
  updateDmDraft,
  type CampaignPlayState,
  type CharacterAcquaintanceView,
} from "../api/client";
import type { NpcFields, NpcView } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import styles from "./Page.module.css";

const statusLabels = {
  PREPARATION: "筹备中",
  ACTIVE: "进行中",
  PAUSED: "已暂停",
  COMPLETED: "已完成",
} as const;

function HpEditor({ campaignId, hp }: { campaignId: string; hp: CampaignPlayState["hpStates"][number] }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(String(hp.currentHp));
  const mutation = useMutation({
    mutationFn: () => updateCampaignHp(campaignId, hp.characterId, Number(value)),
    onSuccess: (data) => queryClient.setQueryData(queryKeys.play(campaignId), data),
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

function RelationshipCard({ pair }: { pair: CharacterAcquaintanceView }) {
  const directions = [pair.aToB, pair.bToA].filter((item) => item != null);
  return (
    <article className={styles.card}>
      <span className={styles.status}>{pair.acquainted ? "已建立关系" : "尚未相识"}</span>
      <h3>{pair.characterAName} ↔ {pair.characterBName}</h3>
      {directions.length === 0 && <p>系统会在双方实际相遇或互动后自动生成关系记录。</p>}
      {directions.map((direction) => (
        <div key={`${direction.ownerCharacterId}:${direction.targetCharacterId}`}>
          <strong>{direction.ownerCharacterName}怎么看{direction.targetCharacterName}</strong>
          <p>{direction.currentView}</p>
          {direction.importantHistory.length > 0 && (
            <ul>
              {direction.importantHistory.map((item) => <li key={item}>{item}</li>)}
            </ul>
          )}
        </div>
      ))}
    </article>
  );
}

function NpcPanel({ campaignId, editable }: { campaignId: string; editable: boolean }) {
  const queryClient = useQueryClient();
  const npcs = useQuery({ queryKey: queryKeys.npcs(campaignId), queryFn: () => listNpcs(campaignId) });
  const [openId, setOpenId] = useState<string | null>(null);
  // Keyed per NPC: a shared buffer leaked one card's edits onto the next.
  const [edited, setEdited] = useState<Record<string, Record<string, string>>>({});
  const draftFor = (npcId: string) => edited[npcId] ?? {};
  const invalidate = async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.npcs(campaignId) }); };
  const extractMutation = useMutation({ mutationFn: () => extractNpcs(campaignId), onSuccess: invalidate });
  const saveMutation = useMutation({
    mutationFn: (npc: NpcView) => updateNpc(npc.id, { revision: npc.revision, ...draftFor(npc.id) }),
    onSuccess: async () => { setEdited({}); setOpenId(null); await invalidate(); },
  });
  const removeMutation = useMutation({ mutationFn: (npcId: string) => deleteNpc(npcId), onSuccess: invalidate });

  const fields: Array<[keyof NpcFields, string]> = [
    ["role", "身份"], ["personality", "个性"], ["ideal", "理想"], ["bond", "牵绊"],
    ["flaw", "缺陷"], ["knows", "知道"], ["wants", "想要"], ["voice", "说话"],
  ];

  return (
    <section className={`${styles.panel} ${styles.form}`}>
      <h2 className={styles.sectionTitle}>出场人物</h2>
      <p className={styles.muted}>
        AI DM 替 NPC 说话时依据的就是这些卡片。从模组自动提取，之后由你说了算——手动改过的卡片不会被重新提取覆盖。
      </p>
      {editable && (
        <div className={styles.formActions}>
          <button className={styles.secondary} disabled={extractMutation.isPending} onClick={() => extractMutation.mutate()} type="button">
            {extractMutation.isPending ? "提取中…" : npcs.data?.length ? "重新从模组提取" : "从模组提取 NPC"}
          </button>
        </div>
      )}
      {extractMutation.error && <p className={styles.error}>{extractMutation.error.message}</p>}
      {npcs.isLoading && <p className={styles.muted}>正在读取…</p>}
      {npcs.data?.length === 0 && <p className={styles.muted}>还没有 NPC 卡片。</p>}
      {npcs.data?.map((npc) => (
        <details key={npc.id} open={openId === npc.id} onToggle={(event) => setOpenId(event.currentTarget.open ? npc.id : null)}>
          <summary>
            {npc.name}
            {npc.role && <span className={styles.muted}> · {npc.role.slice(0, 40)}</span>}
            {npc.source === "DM" && <span className={styles.muted}> · 已手动编辑</span>}
          </summary>
          <div className={styles.form}>
            {fields.map(([key, label]) => (
              <label key={key}>
                {label}
                <textarea
                  disabled={!editable}
                  value={draftFor(npc.id)[key] ?? npc[key]}
                  onChange={(event) => setEdited((current) => ({
                    ...current,
                    [npc.id]: { ...(current[npc.id] ?? {}), [key]: event.target.value },
                  }))}
                />
              </label>
            ))}
            {saveMutation.error && <p className={styles.error}>{saveMutation.error.message}</p>}
            {editable && (
              <div className={styles.formActions}>
                <button className={styles.secondary} disabled={saveMutation.isPending || Object.keys(draftFor(npc.id)).length === 0} onClick={() => saveMutation.mutate(npc)} type="button">保存这张卡</button>
                <button disabled={removeMutation.isPending} onClick={() => removeMutation.mutate(npc.id)} type="button">删除</button>
              </div>
            )}
          </div>
        </details>
      ))}
    </section>
  );
}

export function CampaignDetailPage() {
  const { campaignId } = useParams();
  const queryClient = useQueryClient();
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<string[]>([]);
  const [dmGuide, setDmGuide] = useState("");
  const [sceneNotes, setSceneNotes] = useState("");
  const [moduleContent, setModuleContent] = useState("");
  const [styleInstructions, setStyleInstructions] = useState("");
  const [openingInstructions, setOpeningInstructions] = useState("");
  const [openingContent, setOpeningContent] = useState("");
  const campaign = useQuery({
    queryKey: queryKeys.campaign(campaignId ?? ""),
    queryFn: () => getCampaign(campaignId!),
    enabled: Boolean(campaignId),
  });
  const characters = useQuery({ queryKey: queryKeys.characters, queryFn: listCharacters });
  const play = useQuery({
    queryKey: queryKeys.play(campaignId ?? ""),
    queryFn: () => getCampaignPlayState(campaignId!),
    enabled: Boolean(campaignId) && Boolean(campaign.data?.hasRuntime),
  });
  const acquaintances = useQuery({
    queryKey: queryKeys.acquaintances(campaignId ?? ""),
    queryFn: () => listCampaignAcquaintances(campaignId!),
    enabled: Boolean(campaignId) && (campaign.data?.members.length ?? 0) >= 2,
  });

  useEffect(() => {
    if (campaign.data) {
      setSelectedCharacterIds(campaign.data.members.map((member) => member.characterId));
      setDmGuide(campaign.data.dmGuide);
      setSceneNotes(campaign.data.sceneNotes);
      setModuleContent(campaign.data.moduleContent);
      setStyleInstructions(campaign.data.styleInstructions);
      setOpeningInstructions(campaign.data.openingInstructions);
    }
  }, [campaign.data]);

  async function refreshCampaign() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.campaign(campaignId ?? "") }),
      queryClient.invalidateQueries({ queryKey: queryKeys.play(campaignId ?? "") }),
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns }),
    ]);
  }

  const rosterMutation = useMutation({
    mutationFn: () => replaceCampaignMemberships(campaignId!, campaign.data!.revision, selectedCharacterIds),
    onSuccess: refreshCampaign,
  });
  const activateMutation = useMutation({ mutationFn: () => activateCampaign(campaignId!), onSuccess: refreshCampaign });
  const pauseMutation = useMutation({ mutationFn: () => pauseCampaign(campaignId!), onSuccess: refreshCampaign });
  const resumeMutation = useMutation({ mutationFn: () => resumeCampaign(campaignId!), onSuccess: refreshCampaign });
  const completeMutation = useMutation({ mutationFn: () => completeCampaign(campaignId!), onSuccess: refreshCampaign });
  const deleteMutation = useMutation({
    mutationFn: () => deleteCampaign(campaignId!),
    onSuccess: () => { window.location.assign("/campaigns"); },
  });
  const notesMutation = useMutation({
    mutationFn: () => updateCampaign(campaignId!, {
      revision: campaign.data!.revision,
      dmGuide,
      sceneNotes,
      moduleContent,
      styleInstructions,
      openingInstructions,
    }),
    onSuccess: refreshCampaign,
  });
  const openingDrafts = useQuery({
    queryKey: ["campaigns", campaignId ?? "", "dm-drafts"],
    queryFn: () => listDmDrafts(campaignId!),
    enabled: Boolean(campaignId) && campaign.data?.lifecycleStatus === "PREPARATION",
  });
  const openingMutation = useMutation({
    mutationFn: () => generateOpeningDraft(campaignId!),
    onSuccess: async () => { await openingDrafts.refetch(); },
  });
  const openingDraft = openingDrafts.data?.find((draft) => draft.triggerType === "OPENING" && ["READY", "DRAFT"].includes(draft.status));
  useEffect(() => {
    setOpeningContent(openingDraft?.content ?? "");
  }, [openingDraft?.id, openingDraft?.content]);
  const openingEditMutation = useMutation({
    mutationFn: () => updateDmDraft(openingDraft!.id, {
      revision: openingDraft!.revision,
      content: openingContent.trim(),
      audience: "PUBLIC",
      recipientCharacterIds: [],
    }),
    onSuccess: async () => { await openingDrafts.refetch(); },
  });
  const openingPublishMutation = useMutation({
    mutationFn: () => publishDmDraft(openingDraft!.id),
    onSuccess: refreshCampaign,
  });

  function toggleCharacter(characterId: string) {
    setSelectedCharacterIds((current) =>
      current.includes(characterId)
        ? current.filter((item) => item !== characterId)
        : [...current, characterId],
    );
  }

  if (campaign.isLoading) return <p>正在读取战役…</p>;
  if (campaign.error) return <p className={styles.error}>{campaign.error.message}</p>;
  if (!campaign.data) return null;

  const actionError = rosterMutation.error ?? activateMutation.error ?? pauseMutation.error
    ?? resumeMutation.error ?? completeMutation.error ?? deleteMutation.error ?? notesMutation.error;
  const canActivate = campaign.data.members.length > 0
    && campaign.data.members.every((member) => member.isConfigured)
    && Boolean(moduleContent.trim());
  const isWritablePlay = campaign.data.lifecycleStatus === "ACTIVE";
  return (
    <>
      <Link className={styles.eyebrow} to="/campaigns">← 返回战役列表</Link>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>{statusLabels[campaign.data.lifecycleStatus]}</span>
          <h1>{campaign.data.name}</h1>
          <p>{campaign.data.description || "尚未填写战役简介。"}</p>
        </div>
        <div className={styles.toolbar}>
          {campaign.data.lifecycleStatus === "PREPARATION" && (
            <button className={styles.primary} disabled={!canActivate || activateMutation.isPending} onClick={() => activateMutation.mutate()}>
              启动战役
            </button>
          )}
          {campaign.data.lifecycleStatus === "ACTIVE" && (
            <>
              <button className={styles.secondary} disabled={pauseMutation.isPending} onClick={() => pauseMutation.mutate()}>暂停战役</button>
              <button className={styles.secondary} disabled={completeMutation.isPending} onClick={() => completeMutation.mutate()}>完成战役</button>
            </>
          )}
          {campaign.data.lifecycleStatus === "PAUSED" && (
            <>
              <button className={styles.primary} disabled={resumeMutation.isPending} onClick={() => resumeMutation.mutate()}>继续战役</button>
              <button className={styles.secondary} disabled={completeMutation.isPending} onClick={() => completeMutation.mutate()}>完成战役</button>
            </>
          )}
          {campaign.data.lifecycleStatus === "COMPLETED" && (
            <button className={styles.secondary} disabled={deleteMutation.isPending} onClick={() => {
              if (window.confirm("永久删除战役及其消息、摘要和来源记忆？此操作不可恢复。")) deleteMutation.mutate();
            }}>永久删除</button>
          )}
          {campaign.data.hasRuntime && <Link className={styles.primary} to={`/campaigns/${campaign.data.id}/play`}>进入跑团</Link>}
          <a className={styles.secondary} href={exportUrl("campaign", campaign.data.id)}>导出战役</a>
        </div>
      </header>

      <div className={styles.notice}>一个 Campaign 只有一条连续跑团时间线；暂停和继续不会创建新的 Session。</div>
      {actionError && <p className={styles.error}>{actionError.message}</p>}

      <section className={`${styles.panel} ${styles.form}`}>
        <h2 className={styles.sectionTitle}>{campaign.data.lifecycleStatus === "PREPARATION" ? "模组大纲" : "战役记录"}</h2>
        {campaign.data.lifecycleStatus === "PREPARATION" ? (
          <>
            <p className={styles.muted}>筹备阶段只需要提供模组大纲；AI DM 会据此生成开场和后续叙事草稿。</p>
            <label>模组大纲<textarea disabled={notesMutation.isPending} maxLength={500000} value={moduleContent} onChange={(event) => setModuleContent(event.target.value)} placeholder="主要背景、关键人物、冲突与可能的发展方向…" /></label>
          </>
        ) : (
          <>
            <p className={styles.muted}>进行中可选填当前场景笔记，帮助 AI DM 跟进临时状态。</p>
            <label>当前场景笔记<textarea disabled={campaign.data.lifecycleStatus === "COMPLETED" || notesMutation.isPending} maxLength={100000} value={sceneNotes} onChange={(event) => setSceneNotes(event.target.value)} placeholder="当前地点、未解决线索、临时事实…" /></label>
          </>
        )}
        <div className={styles.formActions}><button className={styles.secondary} disabled={notesMutation.isPending || campaign.data.lifecycleStatus === "COMPLETED"} onClick={() => notesMutation.mutate()} type="button">{notesMutation.isPending ? "保存中…" : "保存资料"}</button></div>
        {campaign.data.lifecycleStatus === "PREPARATION" && (
          <div className={styles.formActions}>
            <button className={styles.primary} disabled={openingMutation.isPending || !moduleContent.trim()} onClick={() => openingMutation.mutate()} type="button">
              {openingMutation.isPending ? "生成开场草稿中…" : "生成 AI DM 开场草稿"}
            </button>
            {openingMutation.error && <p className={styles.error}>{openingMutation.error.message}</p>}
            {openingDrafts.data?.some((draft) => draft.status === "READY") && <p className={styles.muted}>开场草稿已生成，请进入跑团页面编辑并确认发布。</p>}
            {openingDraft && (
              <div className={styles.form}>
                <label>AI DM 开场草稿<textarea maxLength={1200} value={openingContent} onChange={(event) => setOpeningContent(event.target.value)} /></label>
                {(openingEditMutation.error || openingPublishMutation.error) && <p className={styles.error}>{(openingEditMutation.error ?? openingPublishMutation.error)?.message}</p>}
                <div className={styles.formActions}>
                  <button className={styles.secondary} disabled={!openingContent.trim() || openingEditMutation.isPending || openingContent === openingDraft.content} onClick={() => openingEditMutation.mutate()} type="button">保存草稿编辑</button>
                  <button className={styles.primary} disabled={!openingContent.trim() || openingEditMutation.isPending || openingPublishMutation.isPending} onClick={() => openingPublishMutation.mutate()} type="button">确认开团并发送</button>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <NpcPanel campaignId={campaign.data.id} editable={campaign.data.lifecycleStatus !== "COMPLETED"} />

      <h2 className={styles.sectionTitle}>冒险小队 · {campaign.data.memberCount}/6</h2>
      {campaign.data.lifecycleStatus === "PREPARATION" && (
        <div className={`${styles.panel} ${styles.form}`}>
          {characters.isLoading && <p>正在读取角色库…</p>}
          {characters.error && <p className={styles.error}>{characters.error.message}</p>}
          {!!characters.data?.length && (
            <div className={styles.checklist}>
              {characters.data.map((character) => (
                <label className={styles.checkItem} key={character.id}>
                  <input
                    checked={selectedCharacterIds.includes(character.id)}
                    disabled={!selectedCharacterIds.includes(character.id) && selectedCharacterIds.length >= 6}
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
            <button className={styles.secondary} disabled={rosterMutation.isPending} onClick={() => rosterMutation.mutate()} type="button">
              {rosterMutation.isPending ? "保存中…" : "保存阵容"}
            </button>
          </div>
        </div>
      )}

      <div className={styles.grid}>
        {campaign.data.members.map((member) => (
          <article className={styles.card} key={member.characterId}>
            <span className={styles.status}>{member.isConfigured ? "可参加" : "配置未完成"}</span>
            <h3>{member.name}</h3>
            <div className={styles.meta}><span>最大 HP {member.maxHp}</span></div>
          </article>
        ))}
      </div>

      {campaign.data.members.length >= 2 && (
        <section className={`${styles.panel} ${styles.stack}`}>
          <div>
            <h2 className={styles.sectionTitle}>角色关系</h2>
            <p className={styles.muted}>系统根据共同可知的重要互动，分别维护双方对彼此的看法，无需 DM 填写。</p>
          </div>
          {acquaintances.isLoading && <p>正在读取角色相识状态…</p>}
          {acquaintances.error && <p className={styles.error}>{acquaintances.error.message}</p>}
          {acquaintances.data && (
            <div className={styles.grid}>
              {acquaintances.data.map((pair) => (
                <RelationshipCard
                  key={`${pair.characterAId}:${pair.characterBId}`}
                  pair={pair}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {play.isLoading && <p>正在恢复 Campaign 状态…</p>}
      {play.error && <p className={styles.error}>{play.error.message}</p>}
      {play.data && (
        <section className={`${styles.panel} ${styles.stack}`}>
          <div className={styles.toolbar}>
            <strong>连续跑团状态</strong>
            <span className={styles.status}>{isWritablePlay ? "可写入" : "只读"}</span>
            <Link className={styles.primary} to={`/campaigns/${campaign.data.id}/play`}>进入时间线</Link>
          </div>
          {play.data.hpStates.map((hp) => (
            <HpEditor campaignId={campaign.data!.id} hp={hp} key={`${hp.characterId}-${hp.currentHp}`} />
          ))}
        </section>
      )}
    </>
  );
}

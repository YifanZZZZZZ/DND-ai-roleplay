import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { createCharacter, createMemory, deleteMemory, exportUrl, getCharacter, getSkillSet, getSpellbook, listCharacters, listMemories, updateCharacter, updateMemory, updateSkillSet, updateSpellbook, uploadAvatar, type CharacterSpellInput, type SkillSetView } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { CharacterSheetUpload } from "../features/characterSheets/CharacterSheetUpload";
import { SpellbookFields } from "../features/characterSheets/SpellbookFields";
import styles from "./Page.module.css";

function CharacterMemories({ characterId }: { characterId: string }) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const memories = useQuery({ queryKey: queryKeys.memories(characterId), queryFn: () => listMemories(characterId) });
  const mutation = useMutation({
    mutationFn: () => createMemory(characterId, content.trim(), false),
    onSuccess: async () => {
      setContent("");
      await queryClient.invalidateQueries({ queryKey: queryKeys.memories(characterId) });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (memoryId: string) => deleteMemory(characterId, memoryId),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.memories(characterId) }); },
  });
  const updateMutation = useMutation({
    mutationFn: ({ memoryId, nextContent, pinned }: { memoryId: string; nextContent: string; pinned: boolean }) =>
      updateMemory(characterId, memoryId, { content: nextContent, pinned }),
    onSuccess: async () => {
      setEditingId(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.memories(characterId) });
    },
  });
  return <div className={styles.stack}>
    <strong>长期记忆</strong>
    {memories.data?.map((memory) => editingId === memory.id ? (
      <div className={styles.toolbar} key={memory.id}>
        <input defaultValue={memory.content} id={`memory-${memory.id}`} />
        <button type="button" onClick={() => {
          const input = document.getElementById(`memory-${memory.id}`) as HTMLInputElement | null;
          if (input?.value.trim()) updateMutation.mutate({ memoryId: memory.id, nextContent: input.value.trim(), pinned: memory.pinned });
        }}>保存</button>
        <button type="button" onClick={() => updateMutation.mutate({ memoryId: memory.id, nextContent: memory.content, pinned: !memory.pinned })}>{memory.pinned ? "取消固定" : "固定"}</button>
      </div>
    ) : <small key={memory.id}>• {memory.pinned ? "📌 " : ""}{memory.content} <button onClick={() => setEditingId(memory.id)} type="button">编辑</button> <button onClick={() => deleteMutation.mutate(memory.id)} type="button">删除</button></small>)}
    <div className={styles.toolbar}>
      <input placeholder="添加一条角色记忆" value={content} onChange={(event) => setContent(event.target.value)} />
      <button className={styles.secondary} disabled={!content.trim() || mutation.isPending} onClick={() => mutation.mutate()} type="button">添加</button>
    </div>
  </div>;
}

const VOICE_SAMPLE_PLACEHOLDER = "情境：队友受了伤，卡莱拉在给他包扎。\n卡莱拉：（把药膏塞进他手里，视线移开）“自己涂。”停了一下，“……别死在半路上，我懒得埋人。”";

function CharacterEditor({ characterId }: { characterId: string }) {
  const queryClient = useQueryClient();
  const detail = useQuery({ queryKey: ["characters", characterId, "detail"], queryFn: () => getCharacter(characterId) });
  const [prompt, setPrompt] = useState("");
  const [appearance, setAppearance] = useState("");
  const [profile, setProfile] = useState("");
  const [voice, setVoice] = useState("");
  const [narration, setNarration] = useState("");
  const [rules, setRules] = useState("");
  const [bans, setBans] = useState("");
  useEffect(() => {
    if (!detail.data) return;
    setPrompt(detail.data.roleplayPrompt);
    setAppearance(detail.data.appearancePrompt);
    setProfile(detail.data.profileContent);
    setVoice(detail.data.voiceSamples);
    setNarration(detail.data.narrationNotes);
    setRules(detail.data.behaviorRules);
    setBans(detail.data.expressionBans);
  }, [detail.data]);
  const mutation = useMutation({
    mutationFn: () => updateCharacter(characterId, { revision: detail.data!.revision, roleplayPrompt: prompt, appearancePrompt: appearance, profileContent: profile, voiceSamples: voice, narrationNotes: narration, behaviorRules: rules, expressionBans: bans }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.characters }); },
  });
  if (!detail.data) return null;
  return <details className={styles.stack}><summary>编辑角色扮演资料</summary><label>Roleplay Prompt<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label><label>外貌与视觉表现<span className={styles.hint}>填写稳定外貌、服装装备、魔法视觉和习惯性姿态。Agent 只会在当前动作相关时自然带出一两个细节，不会每轮重复完整介绍。</span><textarea value={appearance} onChange={(event) => setAppearance(event.target.value)} /></label><label>说话范例<span className={styles.hint}>3～5 组「情境 → 这个角色会怎么说」。模型模仿的是这里的语气，不是人设里的形容词。</span><textarea placeholder={VOICE_SAMPLE_PLACEHOLDER} value={voice} onChange={(event) => setVoice(event.target.value)} /></label><label>行为规则<span className={styles.hint}>「情境 → 判断 → 行动」，一行一条。形容词只会让模型输出所有同类角色的平均值，可执行的条件-反应对才能把相似的角色分开。</span><textarea value={rules} onChange={(event) => setRules(event.target.value)} /></label><label>绝不会做的事<span className={styles.hint}>这个角色绝不说的话、绝不做的动作。负面约束直接切掉那个「平均角色」最容易滑进去的表达。</span><textarea value={bans} onChange={(event) => setBans(event.target.value)} /></label><label>用词约定<span className={styles.hint}>叙述必须遵守的说法，优先于角色卡。例：他的武器一律称作“长剑”，不要说弯刀。</span><textarea value={narration} onChange={(event) => setNarration(event.target.value)} /></label><label>成长档案<textarea value={profile} onChange={(event) => setProfile(event.target.value)} /></label><button className={styles.secondary} disabled={mutation.isPending} onClick={() => mutation.mutate()} type="button">保存资料</button></details>;
}

const skillNames = [
  "athletics", "acrobatics", "sleight_of_hand", "stealth", "arcana", "history",
  "investigation", "nature", "religion", "animal_handling", "insight", "medicine",
  "perception", "survival", "deception", "intimidation", "performance", "persuasion",
] as const;

const skillLabels: Record<(typeof skillNames)[number], string> = {
  athletics: "运动", acrobatics: "体操", sleight_of_hand: "巧手", stealth: "隐匿",
  arcana: "奥秘", history: "历史", investigation: "调查", nature: "自然", religion: "宗教",
  animal_handling: "驯兽", insight: "洞悉", medicine: "医疗", perception: "察觉", survival: "生存",
  deception: "欺瞒", intimidation: "威吓", performance: "表演", persuasion: "游说",
};

function CharacterSkillsEditor({ characterId }: { characterId: string }) {
  const queryClient = useQueryClient();
  const skills = useQuery({ queryKey: queryKeys.skills(characterId), queryFn: () => getSkillSet(characterId) });
  const [modifiers, setModifiers] = useState<SkillSetView["modifiers"]>({});
  useEffect(() => {
    if (skills.data) setModifiers(skills.data.modifiers);
  }, [skills.data]);
  const mutation = useMutation({
    mutationFn: () => updateSkillSet(characterId, { revision: skills.data!.revision, modifiers }),
    onSuccess: async (data) => {
      queryClient.setQueryData(queryKeys.skills(characterId), data);
    },
  });
  if (skills.isLoading) return <small>正在读取技能加值…</small>;
  if (skills.error) return <small className={styles.error}>{skills.error.message}</small>;
  if (!skills.data) return null;
  return <details className={styles.stack}>
    <summary>十八项技能加值</summary>
    <div className={styles.skillGrid}>
      {skillNames.map((skill) => (
        <label className={styles.skillItem} key={skill}>
          <span>{skillLabels[skill]}</span>
          <input
            aria-label={`${skillLabels[skill]}加值`}
            type="number"
            value={modifiers[skill] ?? 0}
            onChange={(event) => setModifiers((current) => ({ ...current, [skill]: Number(event.target.value) }))}
          />
        </label>
      ))}
    </div>
    {mutation.error && <p className={styles.error}>{mutation.error.message}</p>}
    <button className={styles.secondary} disabled={mutation.isPending} onClick={() => mutation.mutate()} type="button">
      {mutation.isPending ? "保存中…" : "保存技能加值"}
    </button>
  </details>;
}

function CharacterSpellbookEditor({ characterId }: { characterId: string }) {
  const queryClient = useQueryClient();
  const spellbook = useQuery({
    queryKey: queryKeys.spellbook(characterId),
    queryFn: () => getSpellbook(characterId),
  });
  const [spells, setSpells] = useState<CharacterSpellInput[]>([]);
  useEffect(() => {
    if (spellbook.data) setSpells(spellbook.data.spells);
  }, [spellbook.data]);
  const mutation = useMutation({
    mutationFn: () => updateSpellbook(characterId, spellbook.data!.revision, spells),
    onSuccess: async (data) => {
      queryClient.setQueryData(queryKeys.spellbook(characterId), data);
      await queryClient.invalidateQueries({ queryKey: queryKeys.characters });
    },
  });
  if (spellbook.isLoading) return <small>正在读取法术书…</small>;
  if (spellbook.error) return <small className={styles.error}>{spellbook.error.message}</small>;
  if (!spellbook.data) return null;
  const hasIncompleteSpell = spells.some((spell) => !spell.name.trim() || !spell.summary.trim());
  return <details className={styles.stack}>
    <summary>角色法术书 · {spells.length}</summary>
    <span className={styles.hint}>这是 Character Agent 唯一可以使用的法术白名单。修改后立即用于下一次角色回复。</span>
    <SpellbookFields spells={spells} onChange={setSpells} />
    {mutation.error && <p className={styles.error}>{mutation.error.message}</p>}
    <button className={styles.secondary} disabled={mutation.isPending || hasIncompleteSpell} onClick={() => mutation.mutate()} type="button">
      {mutation.isPending ? "保存中…" : "保存法术书"}
    </button>
  </details>;
}

function AvatarUpload({ characterId, avatarPath }: { characterId: string; avatarPath: string | null }) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const mutation = useMutation({ mutationFn: (file: File) => uploadAvatar(characterId, file), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.characters }); } });
  return <div className={styles.toolbar}>{avatarPath && <img alt="角色头像" src={avatarPath} style={{ width: 42, height: 42, objectFit: "cover", borderRadius: "50%" }} />}<input accept="image/png,image/jpeg,image/webp" ref={inputRef} style={{ display: "none" }} type="file" onChange={(event) => { const file = event.target.files?.[0]; if (file) mutation.mutate(file); }} /><button className={styles.secondary} onClick={() => inputRef.current?.click()} type="button">{mutation.isPending ? "上传中…" : "上传头像"}</button></div>;
}

export function CharactersPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [maxHp, setMaxHp] = useState("");
  const [prompt, setPrompt] = useState("");
  const [appearance, setAppearance] = useState("");
  const [voice, setVoice] = useState("");
  const [narration, setNarration] = useState("");
  const characters = useQuery({ queryKey: queryKeys.characters, queryFn: listCharacters });
  const createMutation = useMutation({
    mutationFn: createCharacter,
    onSuccess: async () => {
      setName("");
      setMaxHp("");
      setPrompt("");
      setAppearance("");
      setVoice("");
      setNarration("");
      setShowForm(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.characters });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate({
      name: name.trim(),
      maxHp: Number(maxHp),
      roleplayPrompt: prompt.trim(),
      appearancePrompt: appearance.trim(),
      voiceSamples: voice.trim(),
      narrationNotes: narration.trim(),
      behaviorRules: "",
      expressionBans: "",
    });
  }

  return (
    <>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Persistent Characters</span>
          <h1>全局角色库</h1>
          <p>角色在多个战役之间长期存在；他们的人格、记忆和成长不会绑定到单次冒险。</p>
        </div>
        <button className={styles.primary} onClick={() => setShowForm((value) => !value)}>
          {showForm ? "取消" : "创建角色"}
        </button>
      </header>

      {showForm && (
        <form className={`${styles.panel} ${styles.form}`} onSubmit={submit}>
          <div className={styles.notice}>
            先保存角色核心资料，再上传固定模板 Excel 进行解析预览并确认启用。没有有效角色卡的角色无法启动战役。
          </div>
          <label>
            角色名称
            <input
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label>
            最大 HP
            <input
              required
              min={1}
              type="number"
              value={maxHp}
              onChange={(event) => setMaxHp(event.target.value)}
            />
          </label>
          <label>
            Roleplay Prompt
            <textarea
              required
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
            />
          </label>
          <label>
            外貌与视觉表现（可选）
            <span className={styles.hint}>
              统一按固定轮廓、面部与头发、服装与装备、魔法视觉、习惯性姿态与情境变化五段填写；没有魔法视觉时可以留空。
            </span>
            <textarea
              value={appearance}
              onChange={(event) => setAppearance(event.target.value)}
            />
          </label>
          <label>
            说话范例（可选）
            <span className={styles.hint}>
              3～5 组「情境 → 这个角色会怎么说」。人设描述的是性格，范例决定语气——模型模仿的是后者。
            </span>
            <textarea
              placeholder={VOICE_SAMPLE_PLACEHOLDER}
              value={voice}
              onChange={(event) => setVoice(event.target.value)}
            />
          </label>
          <label>
            用词约定（可选）
            <span className={styles.hint}>
              叙述必须遵守的说法，优先于角色卡上的记录。例：他的武器一律称作“长剑”，不要说弯刀。
            </span>
            <textarea
              value={narration}
              onChange={(event) => setNarration(event.target.value)}
            />
          </label>
          {createMutation.error && <p className={styles.error}>{createMutation.error.message}</p>}
          <div className={styles.formActions}>
            <button
              className={styles.primary}
              disabled={createMutation.isPending || !name.trim() || !prompt.trim() || !maxHp}
            >
              {createMutation.isPending ? "保存中…" : "保存角色资料"}
            </button>
          </div>
        </form>
      )}

      {characters.isLoading && <p>正在读取角色…</p>}
      {characters.error && <p className={styles.error}>{characters.error.message}</p>}
      {characters.data?.length === 0 && !showForm && (
        <EmptyState
          eyebrow="No characters yet"
          title="这里还没有长期角色"
          description="创建角色并填写 Roleplay Prompt；角色卡能力和记忆随后会在同一角色档案中持续累积。"
          action={
            <button className={styles.primary} onClick={() => setShowForm(true)}>
              创建第一个角色
            </button>
          }
        />
      )}
      {!!characters.data?.length && (
        <div className={styles.grid}>
          {characters.data.map((character) => (
            <article className={styles.card} key={character.id}>
              <span className={styles.status}>
                {character.hasActiveSheet ? "角色卡已就绪" : "等待角色卡"}
              </span>
              <h2>{character.name}</h2>
              <AvatarUpload avatarPath={character.avatarPath} characterId={character.id} />
              <div className={styles.meta}>
                <span>最大 HP {character.maxHp}</span>
                <span>{character.hasRoleplayPrompt ? "Prompt 已配置" : "Prompt 缺失"}</span>
              </div>
              <CharacterSheetUpload
                characterId={character.id}
                hasActiveSheet={character.hasActiveSheet}
                onActivated={async () => {
                  await queryClient.invalidateQueries({ queryKey: queryKeys.characters });
                  await queryClient.invalidateQueries({ queryKey: queryKeys.spellbook(character.id) });
                }}
              />
              <CharacterMemories characterId={character.id} />
              <CharacterEditor characterId={character.id} />
              {character.hasActiveSheet && <CharacterSpellbookEditor characterId={character.id} />}
              <CharacterSkillsEditor characterId={character.id} />
              <a className={styles.secondary} href={exportUrl("character", character.id)}>
                导出角色资料
              </a>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

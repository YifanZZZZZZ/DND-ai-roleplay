import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";

import { createCharacter, createMemory, deleteMemory, exportUrl, getCharacter, listCharacters, listMemories, updateCharacter, uploadAvatar } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { CharacterSheetUpload } from "../features/characterSheets/CharacterSheetUpload";
import styles from "./Page.module.css";

function CharacterMemories({ characterId }: { characterId: string }) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
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
  return <div className={styles.stack}>
    <strong>长期记忆</strong>
    {memories.data?.map((memory) => <small key={memory.id}>• {memory.content} <button onClick={() => deleteMutation.mutate(memory.id)} type="button">删除</button></small>)}
    <div className={styles.toolbar}>
      <input placeholder="添加一条角色记忆" value={content} onChange={(event) => setContent(event.target.value)} />
      <button className={styles.secondary} disabled={!content.trim() || mutation.isPending} onClick={() => mutation.mutate()} type="button">添加</button>
    </div>
  </div>;
}

function CharacterEditor({ characterId }: { characterId: string }) {
  const queryClient = useQueryClient();
  const detail = useQuery({ queryKey: ["characters", characterId, "detail"], queryFn: () => getCharacter(characterId) });
  const [prompt, setPrompt] = useState("");
  const [profile, setProfile] = useState("");
  const mutation = useMutation({
    mutationFn: () => updateCharacter(characterId, { revision: detail.data!.revision, roleplayPrompt: prompt, profileContent: profile }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.characters }); },
  });
  if (!detail.data) return null;
  const editedPrompt = prompt || detail.data.roleplayPrompt;
  const editedProfile = profile || detail.data.profileContent;
  return <details className={styles.stack}><summary>编辑角色扮演资料</summary><label>Roleplay Prompt<textarea value={editedPrompt} onChange={(event) => setPrompt(event.target.value)} /></label><label>成长档案<textarea value={editedProfile} onChange={(event) => setProfile(event.target.value)} /></label><button className={styles.secondary} disabled={mutation.isPending} onClick={() => mutation.mutate()} type="button">保存资料</button></details>;
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
  const characters = useQuery({ queryKey: queryKeys.characters, queryFn: listCharacters });
  const createMutation = useMutation({
    mutationFn: createCharacter,
    onSuccess: async () => {
      setName("");
      setMaxHp("");
      setPrompt("");
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
                }}
              />
              <CharacterMemories characterId={character.id} />
              <CharacterEditor characterId={character.id} />
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

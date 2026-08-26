import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";

import {
  activateCharacterSheet,
  previewCharacterSheet,
  type CharacterSpellInput,
  type SheetPreview,
} from "../../api/client";
import { SpellbookFields } from "./SpellbookFields";
import styles from "./CharacterSheetUpload.module.css";

interface CharacterSheetUploadProps {
  characterId: string;
  hasActiveSheet: boolean;
  onActivated: () => Promise<void>;
}

export function CharacterSheetUpload({
  characterId,
  hasActiveSheet,
  onActivated,
}: CharacterSheetUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<SheetPreview | null>(null);
  const [spellbook, setSpellbook] = useState<CharacterSpellInput[]>([]);
  const previewMutation = useMutation({
    mutationFn: (file: File) => previewCharacterSheet(characterId, file),
    onSuccess: (nextPreview) => {
      setPreview(nextPreview);
      setSpellbook(nextPreview.spellbook);
    },
  });
  const activateMutation = useMutation({
    mutationFn: () => activateCharacterSheet(characterId, preview!.versionId, spellbook),
    onSuccess: async () => {
      setPreview(null);
      if (inputRef.current) inputRef.current.value = "";
      await onActivated();
    },
  });

  return (
    <div className={styles.uploader}>
      <input
        ref={inputRef}
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className={styles.fileInput}
        type="file"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) previewMutation.mutate(file);
        }}
      />
      <button
        className={styles.uploadButton}
        disabled={previewMutation.isPending}
        type="button"
        onClick={() => inputRef.current?.click()}
      >
        {previewMutation.isPending
          ? "解析中…"
          : hasActiveSheet
            ? "替换 Excel 角色卡"
            : "上传 Excel 角色卡"}
      </button>

      {previewMutation.error && <p className={styles.error}>{previewMutation.error.message}</p>}
      {activateMutation.error && <p className={styles.error}>{activateMutation.error.message}</p>}

      {preview && (
        <div className={styles.preview}>
          <div>
            <strong>{preview.snapshot.characterName}</strong>
            <span>
              {preview.snapshot.species} · {preview.snapshot.classes.join(" / ")} ·
              {preview.snapshot.background}
            </span>
          </div>
          <dl>
            <div>
              <dt>职业能力</dt>
              <dd>{preview.snapshot.classFeatures?.length ?? 0}</dd>
            </div>
            <div>
              <dt>种族能力</dt>
              <dd>{preview.snapshot.speciesFeatures?.length ?? 0}</dd>
            </div>
            <div>
              <dt>专长</dt>
              <dd>{preview.snapshot.feats?.length ?? 0}</dd>
            </div>
            <div>
              <dt>法术</dt>
              <dd>{preview.snapshot.spells?.length ?? 0}</dd>
            </div>
            <div>
              <dt>装备</dt>
              <dd>{preview.snapshot.equipment?.length ?? 0}</dd>
            </div>
            <div>
              <dt>背包物品</dt>
              <dd>{preview.snapshot.inventory?.length ?? 0}</dd>
            </div>
            <div>
              <dt>技能加值</dt>
              <dd>{Object.keys(preview.snapshot.skills ?? {}).length} / 18</dd>
            </div>
          </dl>
          {Object.keys(preview.snapshot.skills ?? {}).length === 18 && (
            <p className={styles.hint}>确认后将覆盖角色当前的十八项技能加值。</p>
          )}
          <div className={styles.spellEditor}>
            <strong>确认角色法术</strong>
            <p className={styles.hint}>
              已从角色卡和“法术大全”自动读取并转换为无数值摘要。你可以在确认前修改、删除或补充；确认后的内容会成为 Agent 唯一可用的法术白名单。
            </p>
            <SpellbookFields spells={spellbook} onChange={setSpellbook} />
          </div>
          <div className={styles.actions}>
            <button type="button" onClick={() => setPreview(null)}>
              取消
            </button>
            <button
              disabled={activateMutation.isPending || spellbook.some((spell) => !spell.name.trim() || !spell.summary.trim())}
              type="button"
              onClick={() => activateMutation.mutate()}
            >
              {activateMutation.isPending ? "确认中…" : "确认使用这张角色卡"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

import type { CharacterSpellInput } from "../../api/client";
import styles from "./SpellbookFields.module.css";

interface SpellbookFieldsProps {
  spells: CharacterSpellInput[];
  onChange: (spells: CharacterSpellInput[]) => void;
}

const categories = [
  ["CANTRIP", "戏法"],
  ["PREPARED", "已准备"],
  ["AT_WILL", "随意施放"],
  ["MANUAL", "手动记录"],
] as const;

export function SpellbookFields({ spells, onChange }: SpellbookFieldsProps) {
  const update = (index: number, patch: Partial<CharacterSpellInput>) => {
    onChange(spells.map((spell, itemIndex) => itemIndex === index ? { ...spell, ...patch } : spell));
  };

  return (
    <div className={styles.spellbook}>
      {spells.length === 0 && (
        <p className={styles.empty}>当前没有法术。可以手动添加；保持为空代表该角色不会任何法术。</p>
      )}
      {spells.map((spell, index) => (
        <div className={styles.spell} key={`${index}:${spell.name}`}>
          <div className={styles.heading}>
            <input
              aria-label={`法术 ${index + 1} 名称`}
              maxLength={120}
              placeholder="准确法术名称"
              value={spell.name}
              onChange={(event) => update(index, { name: event.target.value })}
            />
            <select
              aria-label={`法术 ${index + 1} 类型`}
              value={spell.category}
              onChange={(event) => update(index, { category: event.target.value })}
            >
              {categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <button type="button" onClick={() => onChange(spells.filter((_, itemIndex) => itemIndex !== index))}>
              删除
            </button>
          </div>
          <textarea
            aria-label={`法术 ${index + 1} 叙事摘要`}
            maxLength={1000}
            placeholder="不含数值的用途、目标、限制和可观察效果"
            value={spell.summary}
            onChange={(event) => update(index, { summary: event.target.value })}
          />
        </div>
      ))}
      <button
        className={styles.add}
        type="button"
        onClick={() => onChange([...spells, { name: "", category: "MANUAL", summary: "" }])}
      >
        添加法术
      </button>
    </div>
  );
}

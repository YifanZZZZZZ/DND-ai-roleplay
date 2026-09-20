# Locked Screenplay Input Schema

Use valid UTF-8 JSON. This file is the machine-readable contract between Story Adapter and later production stages.

## Top-level object

```json
{
  "schema_version": "1.0",
  "project": {},
  "source": {},
  "adaptation_constraints": {},
  "story_core": {},
  "motifs": [],
  "beats": [],
  "screenplay_plan": [],
  "fidelity_constraints": {},
  "unknowns": [],
  "approval": {}
}
```

## Required fields

### project

- `title`: canonical story or video title.
- `language`: output language.
- `output_folder`: absolute or project-relative destination.

### source

- `files`: source paths or supplied-text labels.
- `source_type`: such as `prose`, `character_backstory`, or `treatment`.
- `authorial_perspective`: if known.

### adaptation_constraints

- `target_duration_seconds`: object with integer `min` and `max`.
- `narration_policy`: `none`, `sparse`, or `prominent`.
- `dialogue_policy`: concise description.
- `cost_policy`: concise description of what to compress or avoid.
- `camera_language_allowed`: always `false` in this skill.
- `assumptions`: array of explicit assumptions.

### story_core

- `logline`.
- `protagonist_arc`: ordered array of states.
- `theme`.
- `dramatic_question`.
- `ending_resolution`.

### motifs

Each item contains `motif_id`, `name`, `meaning`, `appearances`, and `continuity_note`.

### beats

Each beat contains:

```json
{
  "beat_id": "B01",
  "title": "Short name",
  "start_state": "State before the event",
  "trigger": "What initiates the change",
  "action": ["Observable action in causal order"],
  "end_state": "State after the event",
  "state_changes": ["emotion", "relationship"],
  "narrative_function": "Why the beat exists",
  "characters": ["Canonical character name"],
  "locations": ["Canonical location label"],
  "time_marker": "Known or inferred time relation",
  "visual_evidence": ["Concrete visible proof"],
  "treatment": "must_show",
  "priority": "core",
  "voiceover_candidates": [],
  "must_preserve": [],
  "may_compress": [],
  "must_not_invent": [],
  "continuity_facts_created": []
}
```

Allowed `treatment` values are `must_show`, `voiceover_candidate`, `montage_candidate`, and `omit_from_video`. Allowed `priority` values are `core`, `required`, and `optional`.

### screenplay_plan

Each planned scene contains:

```json
{
  "scene_id": "S01",
  "title": "Plain-language scene title",
  "beat_ids": ["B01"],
  "dramatic_function": "What changes in this scene",
  "location": "Canonical location",
  "time": "Time of day or relative time",
  "characters": ["Canonical character name"],
  "treatment": "scene",
  "start_visible_state": "What is visibly true at the start",
  "end_visible_state": "What is visibly true at the end",
  "narration_strategy": "none or concise purpose",
  "target_duration_seconds": 12,
  "cost_notes": []
}
```

Allowed scene `treatment` values are `scene`, `montage`, and `transition`.

### fidelity_constraints

- `explicit_facts`: facts that later stages must preserve.
- `prohibited_additions`: invented developments that would change the story.
- `adaptation_freedoms`: changes permitted for compression or visual clarity.

### approval

- `status`: `draft`, `changes_requested`, or `approved`.
- `gate`: `story_confirmation_required` until user approval.
- `open_decisions`: decisions still needing user review.

## Invariants

- Beat IDs and scene IDs are unique and sequential.
- Every `core` and `required` beat is referenced by at least one screenplay scene.
- Every referenced beat exists.
- Planned scene duration totals fit the target duration range or the QC explains the variance.
- Facts absent from the source are not silently converted into locked facts.
- Camera, lens, shot-size, provider, and image-generation fields do not belong in this schema.

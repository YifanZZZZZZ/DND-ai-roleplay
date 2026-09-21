---
name: video-director
description: Turn an approved video screenplay package into a continuity and asset bible, world-space blocking plan, and cost-aware cinematic shot list. Use after story confirmation and before image-asset inventory, image prompting, storyboards, or video generation.
---

# Video Director

Translate an approved story package into production geometry and photographic intent. The downstream Image Asset Prompts skill owns the image list, reference intake, and positive/negative prompts.

## Boundary

Complete these transformations in order:

1. approved screenplay package to Continuity and Asset Bible;
2. screenplay actions to world-space Blocking;
3. Blocking to Shot List;
4. text-only Director QC and downstream handoff.

Stop after the shot plan and continuity contract. Do not build the image-generation queue, collect references, write image prompts, generate images, or make video/audio/editing decisions.

This skill may use film-language fields in the shot list. It must not convert them into provider-specific prompting.

## Required inputs

Prefer the Story Adapter outputs:

- approved `02_locked_screenplay_input.json`;
- `03_video_screenplay.md`;
- optional `04_story_qc.md`.

Require `approval.status` to be `approved`. If it is not approved, stop at the story gate unless the user has explicitly confirmed all open decisions in the current request; in that case, update the approval state before continuing.

Treat the locked JSON as the story source of truth. The screenplay supplies scene prose and timing. Do not reinterpret the raw story or restore material that Story Adapter intentionally compressed.

## Required output package

Write to the established story folder and continue the production numbering:

1. `05_continuity_asset_bible.md` — human-readable characters, locations, props, identity anchors, permitted variations, forbidden variations, and state changes.
2. `06_blocking_plan.md` — scene-by-scene world-space starting positions, action paths, interactions, ending positions, axis, and handoff state.
3. `07_shot_list.md` — ordered shots with duration, shot size, camera height and angle, movement, composition, focus, main action, and continuity dependencies.
4. `08_director_package.json` — normalized downstream source of truth for assets, states, blocking and shots, **without** an image manifest in new schema v2. Read [references/director-package-schema.md](references/director-package-schema.md) before writing it.
5. `09_director_qc.md` — coverage, continuity, spatial, axis, action load, timing, cost, and handoff-readiness checks.

Use stable IDs:

- `CHAR_*` for characters or identity variants;
- `LOC_*` for locations;
- `PROP_*` for recurring props;
- `STATE_*` for continuity states;
- `BLK_*` and `ACT_*` for blocking records and actions;
- `SH###` for shots.
`IMG_*` image IDs are assigned downstream by Image Asset Prompts. Preserve previously approved v1 Director packages with embedded manifests; new v2 packages omit them.

Do not silently overwrite an approved Director package. Preserve it or create a versioned revision unless the user requests replacement.

## Workflow

### 1 Preflight

Verify story approval, source paths, scene IDs, beat coverage, target duration, locked decisions, unknowns, and prohibited additions. Inherit all fidelity constraints.

### 2 Continuity and Asset Bible

Read [references/continuity-blocking-rules.md](references/continuity-blocking-rules.md). Create only assets needed by the approved screenplay.

Give an individually identifiable supporting NPC a character asset and anchor when that person acts, receives a meaningful handoff, or recurs across shots; keep incidental crowds as controlled groups. Preserve each NPC's story function and visible interaction from the approved screenplay. If the user also wants these on-screen NPC anchors for a style-LoRA reference set, record that reuse intent and seek useful visual variety without adding unrelated people or extra film shots. Additional training-only portraits belong to a separately approved asset task, not the required film manifest.

For each character, separate:

- identity anchors that must survive every shot;
- scene or time states such as age, wardrobe, condition, carried items, and emotional baseline;
- allowed variations such as expression and pose;
- forbidden variations that would break identity or chronology.

For each location, define persistent layout, entrances and exits, landmarks, functional zones, time or damage states, and elements that may vary. For recurring props, define ownership, appearance, state transitions, and the shots or actions that change them.

Do not invent precise colors, costume ornament, architecture, or lore when the screenplay does not determine them. Mark those as design choices for later visual development.

### 3 Blocking

Define the world before choosing cameras:

- start positions and facing directions;
- the active interaction axis;
- action units in causal order;
- paths, targets, handoffs, contact, and end positions;
- object and character state changes;
- the exact end state inherited by the next scene or shot.

Use locations and subjects from the Asset Bible. Keep screen-left and screen-right language out of world-space blocking unless it is explicitly derived from a chosen axis. Split simultaneous or overloaded actions into separate `ACT_*` units.

### 4 Shot List

Read [references/shot-list-rules.md](references/shot-list-rules.md). Derive shots from blocking rather than from prose alone.

Treat a `shot` as one independently generated video unit, not every possible editorial cut or story beat. Set a shot budget before drafting. Unless the user explicitly chooses otherwise, each generated shot should be 5–10 seconds, with a target average of 6–8 seconds. Derive the allowed shot-count range from total duration: `ceil(total_seconds / 10)` through `floor(total_seconds / 5)`. Prefer the lower half of that range when story clarity and model capability allow it.

Keep three levels distinct: a screenplay action is what happens, a generated shot is one video-model call, and an editorial emphasis or insert is a possible cut in the final edit. A short editorial cut does not automatically require its own generated clip or keyframe. Conversely, fewer generated shots are not cheaper when they force incompatible locations, time states, or independent actions into one call and increase retries. Optimize expected usable footage and image count, not shot count alone.

Do not create a sub-5-second generated shot merely for an insert, reaction, or conventional edit. Merge that information into a neighboring causal shot. A duration exception requires a specific generation reason, must appear in the budget report, and must be explicitly approved by the user before Director approval.

Each shot should normally contain one primary causal action chain. A tightly coupled setup, action, and immediate reaction may share one shot when location, subjects, axis, and camera logic remain stable. Merge adjacent actions before splitting them. Split only when camera viewpoint must change, time or location changes, the action chain becomes ambiguous, or generation risk rises materially. Use camera movement only when it reveals information, follows necessary motion, changes emotional distance, or preserves spatial comprehension.

Map every essential screenplay action to a shot and inspect the sequence in order for omissions, duplicates, premature end states, and missing visible causes. A time jump, new location/light state, or major prop handoff should be an explicit boundary; do not conceal it inside a continuous clip just to hit the lower shot budget. If a short insert conveys indispensable information, first test whether it can be an editorial crop from an existing clip; otherwise justify a separate generation unit or ask for a duration exception.

Design rhythm at the sequence level: vary observational holds, decisive action, and reaction where the screenplay supports them; establish space before a detail that depends on it; give the central turn and payoff enough screen time to register. These are timing and editorial choices, not a mandate for extra generated shots, keyframes, or uniform rapid cuts.

For each shot, record:

- scene and action coverage;
- duration;
- shot size;
- camera height and angle;
- movement;
- composition and focus;
- subjects, location, and required props;
- visible start state, primary action, and visible end state;
- axis side and continuity dependencies;
- motion complexity and generation risk;
- whether the end state is significant enough for the next stage to consider an end keyframe.

Do not write image or video prompts. Do not assume every shot needs two keyframes.

Before approval, report the computed shot-count range, proposed shot count, average duration, every duration exception, distribution by scene, and the estimated Start/End Frame count. If the count exceeds the budget or any shot falls outside 5–10 seconds, provide a merge map and obtain user confirmation rather than silently locking the longer list.

### 5 Image-planning handoff

For each shot, state its identifiable subjects, location, props, start state, action, end state, visual continuity dependencies, and whether the end state is unusually precise. Keep identity, age, wardrobe, creature, prop, and layout constraints in the Asset Bible. Do **not** classify assets by whether a user has reference images; that decision happens on the downstream upload page.

The next skill, Image Asset Prompts, combines the screenplay and this shot plan to enumerate all character/scene anchors and selective Start/End Frames. It must not silently change the Director shots. Unresolved design choices remain explicit for that stage and the user's review.

### 6 Validate and QC

Run:

```bash
python scripts/validate_director_package.py <path-to-08_director_package.json>
```

Fix structural failures before delivery. Then check:

- every approved scene and required screenplay action is covered;
- all referenced assets and actions exist;
- per-scene and total shot durations match the screenplay plan;
- positions, facing, props, wardrobe, damage, time, and emotional state remain continuous;
- the 180-degree axis is maintained or a motivated reset is documented;
- no shot contains an overloaded action chain;
- essential screenplay actions are covered in causal order, including the on-screen action that makes an emotional payoff legible;
- shots with time, place, or lighting changes have explicit boundaries instead of relying on an unexplained transition inside one clip;
- camera movement has a narrative or spatial reason;
- shots with high generation risk are split or explicitly justified;
- later stages can identify likely start-only versus start-and-end keyframe candidates without changing story logic.
- the shot count is inside the duration-derived budget and all shots are 5–10 seconds unless the user explicitly approved named exceptions;
- every individually identifiable NPC in the screenplay has a consistent asset/state path, while background extras have not been promoted into costly portraits without a visible purpose;
- shot fields and continuity states are complete enough for the downstream skill to enumerate image requirements without rereading the raw story.

End with a **Director Confirmation Gate** for story geometry, continuity, shot count, and cost. The next Image Asset Prompts skill consumes the approved `08_director_package.json`; Storyboard QC comes only after reference intake and prompt-package approval.

## Partial requests

If the user requests only an Asset Bible, Blocking plan, or Shot List, create only the requested layer and its prerequisites. Clearly mark the package incomplete and do not imply that downstream generation is ready.

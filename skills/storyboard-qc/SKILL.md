---
name: storyboard-qc
description: Review an Image Asset Prompts package with strict one-image-at-a-time human approval, targeted retries, and continuity QC. Use after reference intake and prompt generation; also supports legacy Director image manifests.
---

# Storyboard QC

Convert an approved screenplay/Director plan and the Image Asset Prompts package into visually locked anchors and storyboard keyframes through a strict serial human-in-the-loop review queue. Existing projects may still use a legacy Director v1 manifest.

## Boundary

This skill owns:

1. text-level preflight for narrative, continuity, spatial logic, camera logic, timing, and generation risk;
2. visual design resolution for `design_choice_pending` fields;
3. image-prompt package validation and queue initialization;
4. one-at-a-time image generation;
5. explicit human approval or targeted retry for every image;
6. final sequence continuity QC after all required items are individually approved.

It does not create or revise story beats, blocking, shots, the required image list, provider-specific video prompts, proxy videos, final videos, voiceovers, music, subtitles, or edit decisions. Structural changes return to the upstream skill.

## Required inputs

Prefer:

- approved `08_director_package.json` and `image-prep/image-prompt-package_vNN.json` with status `awaiting_prompt_review`;
- `image-prep/asset-intake.json`, including uploaded reference paths and revision;
- the matching `image-prep/image-prompts_vNN.md`;
- `05_continuity_asset_bible.md`;
- `06_blocking_plan.md`;
- `07_shot_list.md`;
- optional `09_director_qc.md`.

Require Director `approval.status` to be `approved`. Require a fresh prompt package whose `source_reference_revision` matches intake. Inherit all story and Director constraints. Do not redesign blocking, shots, or the required image list merely to make image generation easier. For a legacy Director v1 package, its embedded `image_generation_manifest` and `08_image_generation_manifest.md` remain an accepted alternative.

## Human-in-the-loop gates

Planning and text QC may run immediately. Actual image generation is gated, serial, and individually reviewed.

### Gate A Visual Design and Prompt-Package Confirmation

Before generating images, present and obtain confirmation for:

- visual style and world design;
- every unresolved primary character and location choice;
- the complete five-category image-prompt package, exact image count, and each positive/negative prompt;
- intended image dimensions or aspect ratios when known;
- which generation tool or model will be used.
- for each character, location, group, or prop anchor: whether to use an existing reference directly, generate normalized or state-specific anchors from supplied references, or generate the anchor from scratch;
- the exact local files supplied for each reference choice and which views or states they cover.

If the user supplied a character sheet or named a target medium, explicitly compare the intended visual style and character identity (including stated gender presentation, age-state relationship, hairstyle, and costume role) against that source before authorizing a derived image. Do not infer gender or personality from long hair, ornaments, or clothing alone. Record a mismatch as a design decision rather than allowing the image model to settle it independently.

When approved NPC anchors are also intended as style-LoRA reference material, review them for shared rendering language and distinct silhouettes, face shapes, age presentations, and costumes as permitted by the Director design brief. An on-screen NPC must still pass film continuity and story-role QC; style-dataset reuse does not authorize adding images to the fixed manifest or bypassing per-image approval.

The batch Prompt button does not approve prompts, references, or image-generation spend. Obtain explicit Gate A confirmation before the first image candidate.

### Reference source modes

For every anchor requirement, let the user choose:

- `use_existing_reference`: copy or register the supplied image in `visual-assets/references/`, review it as the anchor, and generate no replacement;
- `generate_from_reference`: register the supplied reference, then generate only missing normalized views, age states, costumes, expressions, or pose variants while preserving identity;
- `generate_new`: create a new anchor from the approved design brief.

A character turnaround or three-view sheet is a first-class reference input. Map its front, side, back, and optional three-quarter views to one source record. Do not collapse it into a textual description. Record the original path, linked asset ID, covered states, visible views, and human approval. Downstream frames must cite the approved source or derived anchor ID.

### Gate B Per-Image Human Review

After Gate A, process exactly one manifest item at a time. Generate one candidate, show that candidate with its ID and acceptance criteria, and stop for the user's explicit decision. The only decisions are:

- `approved`: freeze the selected attempt and advance to the next queue item;
- `retry_requested`: keep the failed attempt, record the defect and invariants to preserve, generate a new version of the same item, and stop again for review;
- `rejected`: stop the queue and return the item or its prerequisites upstream for revision.

Never infer approval from silence, from a Contact Sheet, from approval of another image, or from a generic instruction to continue when a specific image is awaiting judgment. Never have more than one item in `generated_waiting_review`.

### Gate C Final Sequence Review

After every required manifest item is individually approved, create Contact Sheets for overview and perform sequence continuity QC. Contact Sheets do not replace per-image approvals. The next skill may proceed only after final storyboard approval.

## Required output package

Write planning and QC files to the established story folder:

1. `10_storyboard_preflight.md` — textual diagnostics and any required Director revisions.
2. `11_image_review_queue.md` — categorized prompt-package queue, dependencies, cost count, and live per-item review status.
3. `12_frame_specs.md` — model-neutral visual specifications derived from the confirmed prompt package; it cannot add or remove required IDs.
4. `13_storyboard_package.json` — machine-readable queue, attempts, and human decisions. Read [references/storyboard-package-schema.md](references/storyboard-package-schema.md).
5. `14_storyboard_qc.md` — individual approvals, targeted retry history, and final sequence review.

Use this folder layout:

```text
visual-assets/
  references/
    characters/
    locations/
    props/
  anchors/
    characters/
    groups-creatures/
    locations/
    props/
  keyframes/
    start/
    end/
  contact-sheets/
```

Keep every generated file linked to a stable manifest image ID and immutable attempt ID. Use versioned filenames such as `IMG_CHAR_001_v01.png`; never overwrite an attempt.

## Workflow

### 1 Preflight

Check the approved Director package before any image work:

- story and beat coverage;
- character, location, prop, wardrobe, age, damage, and time continuity;
- blocking, travel direction, gaze, handoff, and axis logic;
- unnecessary camera movement, shot action load, duration, and generation risk;
- whether pending design choices block the first dependency-ready item;
- whether the prompt package is fresh, complete, and its five category counts are correct.
- whether the opening image sequence makes the story's source-grounded promise legible and whether the planned payoff remains visible rather than existing only in narration;
- whether any frame specification quietly asks one still image or one continuous shot to span incompatible time, location, or action states.

If a problem requires changing story, blocking, shots, or required image membership, stop that affected branch and request the smallest upstream revision. Do not hide it inside an image prompt.

### 2 Validate and initialize the image queue

Read [references/visual-anchor-rules.md](references/visual-anchor-rules.md) and [references/keyframe-qc-rules.md](references/keyframe-qc-rules.md). Verify that the prompt package contains the smallest sufficient anchors, exactly one Start Frame per shot, selective justified End Frames, resolvable dependencies, and a complete cost count.

Do not silently repair a deficient package. Copy prompt-package IDs into `review_queue` without changing their order. During Gate A, confirm each positive/negative prompt and resolve every anchor's `fulfillment_mode`. Register the files selected on the intake page; do not ask for all uploads again. A referenced anchor may use an existing image or generate from reference; an unreferenced anchor uses `generate_new`. Initialize every item as `pending`; at most the first dependency-ready item may become `authorized`.

Write model-neutral image specifications before provider adaptation. Resolve visual choices explicitly rather than allowing independent images to decide them differently.

### 3 Strict serial generation and human review

Only after Gate A approval, use the available image-generation capability for the current queue item. When an image-generation skill is available, follow it for actual generation or edits.

For each item, in queue order:

1. Verify every dependency item is already `approved`.
2. If the selected mode is `use_existing_reference`, ingest and display that reference as the current candidate without calling image generation; require the same explicit human approval.
3. If the selected mode is `generate_from_reference`, pass all approved source views to the image-generation skill and state exactly which identity features must remain unchanged.
4. If the selected mode is `generate_new`, generate from the approved model-neutral brief.
5. Authorize exactly one item and create exactly one new attempt or reference-review record.
6. Record output or source path, dimensions, generator or `user_supplied`, generation-settings reference, and automated QC notes.
7. Set the item to `generated_waiting_review` or `reference_waiting_review`, display the image, list `must_show` and `must_not_show`, and ask the user to approve, request a retry or replacement, or reject.
   For a derived character anchor, call out the identity traits held fixed and the one intended change; for a frame, call out its visible start state and any forbidden premature end state. Distinguish a supplied `REF_*` file, a planned `IMG_*` requirement, and a generated attempt—never describe a missing planned file as an existing image.
8. Stop the run until the user answers for that exact image ID.
9. On approval, record an explicit human decision, set `approved_attempt_id`, freeze the source, and authorize only the next dependency-ready item.
10. On retry, preserve the prior version, record one precise defect and invariants to preserve, then create or ingest the next version.
11. On rejection, set the queue to `blocked_upstream_revision` and do not advance.

Never regenerate an approved item unless the user explicitly revokes its approval. Record revocation and return every dependent downstream item to `pending_revalidation`.

Anchors naturally come first because Shot Frames depend on them. There is no batch anchor approval that can substitute for approval of each anchor.

After the first representative character and location anchors, and again after the first completed scene's approved frames, offer a small read-only style/continuity preview before producing many more items. This is an early error check, not a batch-generation or batch-approval shortcut; any correction still reopens only the affected manifest item with explicit user input.

### 4 Frame specification

Every Start/End Frame already exists in the Image Asset Prompts package. Expand each into a model-neutral frame specification without changing the image list. If an End Frame decision appears wrong, stop and request an upstream image-plan or Director revision.

Preserve axis side, screen direction, subject order, eyelines, wardrobe, props, lighting state, location layout, and the approved anchor dependencies. Do not generate video in this stage.

### 5 Final sequence QC

Only after every required item has an explicit `approved` human decision:

- create anchor and storyboard Contact Sheets for overview;
- compare each newly approved frame with its approved neighboring frames as the queue advances, and perform a final ordered sequence review after all items are approved; these read-only continuity checks never substitute for the user's per-image decision;
- review storyboard frames in shot order;
- if a sequence defect is found, identify the smallest failed item, revoke only that approval with the user's confirmation, and reopen its serial retry loop;
- approve the overall storyboard only when no required item or retry remains unresolved.

### 6 Validate and hand off

Run:

```bash
python scripts/validate_storyboard_package.py <path-to-13_storyboard_package.json>
```

Use `--check-files` after images have been generated.

Allowed stages are `planned`, `in_review`, `blocked_upstream_revision`, `all_items_approved`, and `approved`.

The next Generation Planner skill consumes only an approved storyboard package. Validation must fail if a required image item lacks an approved human decision, if two items are simultaneously awaiting review, or if a later item advanced before an earlier required item.

## Partial requests

If the user requests planning only, complete preflight, queue initialization, and frame specifications without generating images. If image generation begins, process only the current item and stop at its human review gate. Never infer approval for a later item from approval of an earlier one.

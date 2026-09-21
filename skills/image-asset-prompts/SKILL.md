---
name: image-asset-prompts
description: Build a complete image-asset inventory from an approved screenplay and Director shot list, collect character and scene references in one local intake page, then batch-create positive and negative prompts for five image classes. Use after Video Director and before Storyboard QC; do not generate or approve images.
---

# Image Asset Prompts

Turn a locked story and Director shot plan into an image-prompt package in two deliberate phases: **reference intake first, prompt generation second**. One click may generate all *text prompts*; it never generates images or approves their visual quality.

## Inputs and boundary

Read the approved screenplay, shot list, Director package, and any existing continuity/asset bible. Require story and Director approval for a production-ready package. A draft may be processed for a labeled review/test, but cannot be marked ready for Storyboard QC. Preserve shot IDs, visual state, blocking, axis, and the Director shot budget. Do not revise screenplay or shots to simplify prompts.

This skill owns the complete **image requirement list**, reference intake, and image prompts. Video Director owns story geometry and shot decisions, not the image manifest or prompts. Storyboard QC owns image generation, one-image-at-a-time approval, retries, and final sequence QC. Do not upload assets to a cloud provider, run an image model, spend generation credits, or infer user approval here.

## Phase 1 — inventory and intake page

1. From every shot and its scene, enumerate all recognizable character/age/wardrobe states, recurring creatures, locations/time states, and continuity-critical standalone props. Treat recurring creatures as characters. To keep the user's five output classes, list standalone props as `scene_support` rows inside the scene intake and retain their Director `PROP_*` IDs; do not silently omit them.
2. Deduplicate by identity and state. Incidental crowds, one-shot rabbits, and minor dressing remain within scene/frame briefs unless independent continuity actually requires an anchor. Give every required shot exactly one Start Frame; include an End Frame only when a precise transformation, handoff, healing, damage, or final spatial state cannot be trusted to the Start Frame plus action alone. Record the reason.
3. Create `image-prep/asset-intake.json` using [the intake schema](references/intake-and-prompt-schema.md). Include actor/scene rows and internal shot-frame briefs, but **no positive or negative prompts**. The first visible page contains only the complete character and scene/support list, required views/states, shot coverage, and optional upload/notes controls. Do not show Start/End Frame rows at this phase.
   Keep `style_brief` strictly about rendering medium, linework, palette, texture, and lighting. Put hairstyle, hair/eye color, ears, age, face, costume, and other identity traits only in the corresponding entity row. Before generating prompts, read the shared style text as if it were appended to **every** person and scene; if it would describe the wrong subject, fix the intake first. A negative prompt does not cancel a contradictory positive prompt.
4. Start the local page with `python scripts/intake_app.py serve <story-folder>/image-prep/asset-intake.json`. The page accepts multiple user reference images per row, saves them under the story folder, shows thumbnails and upload status, and permits removing a file from the selection without deleting it from disk. If a row has at least one uploaded reference at final confirmation, classify it as **有素材人物** or **有素材场景**; otherwise classify it as **无素材人物** or **无素材场景**. No upload is a valid deliberate choice.
5. Wait for the user to finish uploads and explicitly tick “已完成全部参考图选择”. Uploads can be completed across all rows before a single batch action. Any upload or note change after generation makes the prompt package stale and requires regeneration; preserve old versioned outputs.

The page layout and API behavior are specified in [the intake schema](references/intake-and-prompt-schema.md); the shipped `assets/intake.html` is the reusable page, not a mockup. The local script does not call an external model. Prompt quality depends on the complete visual briefs authored from the screenplay/Director package; do not leave unexplained placeholders in a production-ready inventory.

## Phase 2 — one-click batch prompt generation

The page's **生成全部 Prompt** button creates `image-prep/image-prompt-package_vNN.json` and `image-prep/image-prompts_vNN.md` through the local script. Generate both positive and negative prompts for every image in exactly these five top-level classes:

1. `person_with_reference` — includes recognizable creatures; cite the exact uploaded files and what they define.
2. `person_without_reference` — create identity from the approved visual brief; no fictitious source image.
3. `scene_with_reference` — includes `scene_support` props; preserve source layout/object identity and cite files.
4. `scene_without_reference` — construct from screenplay, blocking, and visual bible.
5. `shot_frame` — Start and selectively justified End Frames; link character/scene dependencies, source refs, camera, exact visible state, and forbidden premature or reverted state.

The five classes are prompt routing labels, not five batches of image generation. Each item retains its stable `IMG_*` ID, Director asset/state IDs, shot ID where applicable, dependency IDs, `must_show`, `must_not_show`, intended aspect ratio, positive prompt, negative prompt, and reference paths. Generation order is anchor prompts first, then Start/End Frames in shot order. Every shot has one Start Frame. An End Frame depends on its Start Frame.

Do not treat “有素材” as automatic image approval: a reference can be used as-is only if it meets the anchor criteria and Storyboard QC obtains explicit user approval. A reference image may alternatively guide a newly generated anchor. The prompt package is text-only and remains `draft_review` while upstream approvals or design choices are open. With upstream approvals it becomes `awaiting_prompt_review`; Storyboard QC Gate A must confirm the prompts before generating images.

Validate with `python scripts/intake_app.py validate <story-folder>/image-prep/asset-intake.json` before opening the page and again after batch generation. Inspect the generated prompt package for source/shot coverage, empty prompts, contradictory negative terms, age/wardrobe drift, layout drift, and incorrect reference lineage. Revise the structured briefs and regenerate a new version if the deterministic page output is too generic; do not hand off low-quality placeholders.
In particular, spot-check one NPC and one scene prompt for leaked protagonist-only traits from `style_brief`; if present, reject the whole batch, correct the intake, and generate a new version rather than patching only the displayed prompt.

## Handoff

Storyboard QC consumes the `awaiting_prompt_review` image-prompt package as its immutable proposed image list and prompt source, confirms it with the user at Gate A, and then processes **one candidate image at a time** at Gate B. Prompt-batch approval does not authorize batch image generation. Preserve legacy Director manifests for existing projects; never silently overwrite an already approved package.

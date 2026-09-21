# Storyboard Package Schema

Use valid UTF-8 JSON. `13_storyboard_package.json` is the audit trail for a strict serial human-in-the-loop image queue. New projects use schema v3 sourced from Image Asset Prompts. Legacy Director-manifest projects retain schema v2.

## Top-level object

```json
{
  "schema_version": "3.0",
  "project": {},
  "source_director_package": {},
  "source_image_prompt_package": {},
  "stage": "planned",
  "preflight": {},
  "visual_design": {},
  "reference_sources": [],
  "cost_gate": {},
  "review_queue": [],
  "attempts": [],
  "human_decisions": [],
  "contact_sheets": [],
  "approval": {}
}
```

## source_director_package

Required fields:

- `file`;
- `approval_status`: must be `approved`;
- `shot_count` and `duration_seconds`;
- `inherited_constraints`.

For v3, `source_image_prompt_package` has `file`, `status: awaiting_prompt_review`, `item_count`, and `source_reference_revision`. Its ordered `items[].image_id` are copied exactly into `review_queue`, including each item's `positive_prompt` and `negative_prompt`. Gate A must confirm that package. Legacy v2 instead uses Director `manifest_version`, `manifest_item_count`, and `manifest_image_ids`.

## stage

Allowed values are `planned`, `in_review`, `blocked_upstream_revision`, `all_items_approved`, and `approved`.

## preflight and visual_design

`preflight` contains `status`, `checks`, `warnings`, `blocking_issues`, and `upstream_revisions_required`. The queue cannot begin while a blocking issue exists.

`visual_design` records the confirmed style, world, architecture, material, palette, identity, costume, location, and image-format decisions. Use `status: pending` until Gate A is explicitly approved.

## reference_sources

Each supplied reference is registered without altering the original:

```json
{
  "reference_id": "REF_CHAR_LAESER_001",
  "asset_id": "CHAR_LAESER_ADULT_01",
  "source_files": ["visual-assets/references/characters/laeser_turnaround.png"],
  "source_type": "three_view_sheet",
  "visible_views": ["front", "side", "back"],
  "covered_state_ids": ["STATE_CHAR_LAESER_ADULT_EARLY_CAMP"],
  "status": "pending_human_review"
}
```

Allowed source types include `three_view_sheet`, `turnaround`, `portrait`, `full_body`, `environment_concept`, `layout`, and `prop_sheet`. A source becomes usable only after explicit human approval.

## cost_gate

```json
{
  "manifest_confirmed": false,
  "image_generation_authorized": false,
  "authorized_image_ids": [],
  "estimated_visual_requirements": 0,
  "estimated_new_generations_min": 0,
  "estimated_new_generations_max": 0
}
```

Authorization is narrow: during serial execution `authorized_image_ids` contains at most the current item. Authorization for one item does not authorize later items.

## review_queue

Copy every Image Asset Prompts item in the same order and add review state (or copy the Director manifest for legacy v2):

```json
{
  "image_id": "IMG_SH001_START",
  "category": "shot_frame",
  "required": true,
  "dependencies": ["IMG_CHAR_001", "IMG_LOC_001"],
  "planned_output_path": "visual-assets/keyframes/start/IMG_SH001_START_v01.png",
  "must_show": [],
  "must_not_show": [],
  "positive_prompt": "...",
  "negative_prompt": "...",
  "allowed_fulfillment_modes": ["use_existing_reference", "generate_from_reference", "generate_new"],
  "fulfillment_mode": "unselected",
  "reference_ids": [],
  "status": "pending",
  "attempt_ids": [],
  "approved_attempt_id": null
}
```

Allowed status values:

- `pending`;
- `authorized`;
- `generated_waiting_review`;
- `reference_waiting_review`;
- `retry_requested`;
- `approved`;
- `rejected`;
- `pending_revalidation`.

At most one item may be `authorized`, `generated_waiting_review`, `reference_waiting_review`, or `retry_requested`. A later item must remain `pending` until every earlier required item is `approved`. Dependencies must also be `approved`.

## attempts

Each generation attempt is immutable:

```json
{
  "attempt_id": "ATT_IMG_SH001_START_v01",
  "image_id": "IMG_SH001_START",
  "version": 1,
  "file": "visual-assets/keyframes/start/IMG_SH001_START_v01.png",
  "width": 1920,
  "height": 1080,
  "generator": "imagegen",
  "generation_settings_ref": "GENSET_001",
  "automated_qc_notes": [],
  "status": "waiting_human_review"
}
```

`generator` may be `user_supplied` for `use_existing_reference`. Allowed attempt statuses are `waiting_human_review`, `approved`, `superseded`, and `rejected`. Version numbers for each image ID start at 1 and increase without gaps. Files are never overwritten.

## human_decisions

Every decision identifies one attempt:

```json
{
  "decision_id": "DEC_0001",
  "image_id": "IMG_SH001_START",
  "attempt_id": "ATT_IMG_SH001_START_v01",
  "decision": "approved",
  "defect": null,
  "preserve": [],
  "requested_change": null,
  "recorded_from_user": true
}
```

Allowed decisions are `approved`, `retry_requested`, `rejected`, and `approval_revoked`. An approval is valid only when `recorded_from_user` is true. A retry requires a precise `defect`, `preserve`, and `requested_change`.

## contact_sheets

Contact Sheets are optional overview artifacts. Each record contains `sheet_id`, `type`, `file`, `included_image_ids`, `status`, and `review_notes`. Their status cannot approve individual images.

## approval

- `status`: `draft`, `changes_requested`, or `approved`;
- `gate`: `visual_design_and_manifest_confirmation_required`, `image_review_required`, `upstream_revision_required`, `final_sequence_confirmation_required`, or `storyboard_confirmed`;
- `current_review_image_id`: null or the one active item;
- `open_decisions`.

## Invariants

- Director approval is `approved`; v3 copies the image-prompt package order exactly, while legacy v2 copies the Director manifest order.
- Queue image IDs are unique and match their chosen source package exactly.
- Every anchor selects one allowed fulfillment mode before review; supplied references have stable IDs and explicit human approval.
- `use_existing_reference` calls no image generator; `generate_from_reference` records reference lineage.
- At most one item is active or awaiting review.
- Items advance strictly in queue order; dependencies and all earlier required items are approved first.
- Every generated file belongs to one immutable versioned attempt.
- Every approved queue item has exactly one current approved attempt and an explicit human `approved` decision.
- Retry attempts preserve prior files and record a precise failure reason.
- An approved storyboard has all required queue items approved, no active or unresolved item, and explicit final sequence approval.

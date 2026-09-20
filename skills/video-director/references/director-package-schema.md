# Director Package Schema

Use valid UTF-8 JSON. `08_director_package.json` is the machine-readable contract between Video Director and Image Asset Prompts. New packages use v2, which deliberately has no image manifest. Existing v1 packages with an embedded manifest remain valid legacy inputs.

## Top-level object

```json
{
  "schema_version": "2.0",
  "project": {},
  "source_package": {},
  "director_constraints": {},
  "scenes": [],
  "assets": {
    "characters": [],
    "locations": [],
    "props": []
  },
  "world_states": [],
  "blocking": [],
  "shots": [],
  "approval": {}
}
```

The remainder of this document describes the shared Director fields. Its `image_generation_manifest` section applies **only to legacy v1** packages. Do not include that key in v2. The downstream Image Asset Prompts skill derives image IDs, reference intake, and prompts from the approved screenplay plus this Director package.

## Required objects

### source_package

- `locked_input_file`, `screenplay_file`, and optional `story_qc_file`.
- `story_approval_status`: must be `approved`.
- `inherited_fidelity_constraints`: carry forward the locked story constraints.

### director_constraints

- `target_duration_seconds`.
- `cost_policy`.
- `axis_policy`.
- `action_load_policy`.
- `prompt_generation_allowed`: always `false`.
- `assumptions`.
- `shot_budget`: `min_shot_duration_seconds`, `max_shot_duration_seconds`, `target_average_min_seconds`, `target_average_max_seconds`, computed `shot_count_min`, computed `shot_count_max`, `proposed_count`, `average_duration_seconds`, `duration_exceptions`, `merge_rationale`, and whether any exception has explicit user approval.

### scenes

Each scene contains `scene_id`, `title`, `beat_ids`, `duration_seconds`, `location_ids`, `character_ids`, and `time_state`.

### assets.characters

Each character asset contains:

```json
{
  "asset_id": "CHAR_PROTAGONIST_01",
  "name": "Canonical name",
  "role": "protagonist",
  "identity_anchors": [],
  "design_choices_pending": [],
  "allowed_variations": [],
  "forbidden_variations": [],
  "states": [
    {
      "state_id": "STATE_CHAR_PROTAGONIST_ADULT",
      "scene_ids": ["S02"],
      "age_phase": "adult",
      "wardrobe": "design_choice_pending",
      "condition": [],
      "carried_prop_ids": [],
      "emotional_baseline": "",
      "continuity_notes": []
    }
  ],
  "reference_priority": "primary"
}
```

Allowed `reference_priority` values: `primary`, `secondary`, `group`, `none`.

### assets.locations

Each location contains `asset_id`, `name`, `scene_ids`, `fixed_layout`, `entrances_exits`, `landmarks`, `states`, `allowed_variations`, `forbidden_variations`, and `reference_priority`.

Location states contain `state_id`, `scene_ids`, `time`, `weather`, `occupancy`, `condition`, `lighting_notes`, and `continuity_notes`.

### assets.props

Each prop contains `asset_id`, `name`, `owner_or_home`, `scene_ids`, `identity_anchors`, `states`, `state_transitions`, and `reference_priority`.

### world_states

Each record contains `state_id`, `after_scene_id`, `character_states`, `location_states`, `prop_states`, and `facts_carried_forward`.

### blocking

Each blocking record contains:

```json
{
  "blocking_id": "BLK_S01",
  "scene_id": "S01",
  "location_id": "LOC_ROOM_01",
  "coordinate_convention": "Door is north; table is center.",
  "axis": {
    "description": "Dominant relation or travel line",
    "side_rule": "Camera remains on the south side",
    "reset_allowed": false,
    "reset_method": "none"
  },
  "start_positions": [],
  "actions": [
    {
      "action_id": "ACT_S01_01",
      "performer_ids": ["CHAR_PROTAGONIST_01"],
      "action": "One observable action",
      "target_ids": ["PROP_OBJECT_01"],
      "path": "Concrete world-space path or none",
      "end_position": "Concrete relation to landmarks",
      "state_changes": [],
      "complexity": "low",
      "must_be_visible": true
    }
  ],
  "end_positions": [],
  "continuity_handoff": [],
  "spatial_risks": []
}
```

Allowed action complexity values: `low`, `medium`, `high`.

### shots

Each shot contains:

```json
{
  "shot_id": "SH001",
  "scene_id": "S01",
  "action_ids": ["ACT_S01_01"],
  "source_shot_ids": ["OLD_SH001"],
  "action_chain_rationale": "",
  "narrative_purpose": "",
  "duration_seconds": 4,
  "shot_size": "medium",
  "camera_height": "eye level",
  "camera_angle": "neutral",
  "perspective": "natural",
  "camera_movement": "fixed",
  "movement_reason": "none",
  "composition": "",
  "focus": "",
  "subject_ids": ["CHAR_PROTAGONIST_01"],
  "location_id": "LOC_ROOM_01",
  "prop_ids": ["PROP_OBJECT_01"],
  "start_visible_state": "",
  "primary_action": "",
  "end_visible_state": "",
  "axis_side": "south",
  "continuity_dependencies": [],
  "motion_complexity": "low",
  "generation_risk": "low",
  "risk_notes": [],
  "end_state_significance": "medium"
}
```

Allowed values:

- `motion_complexity`, `generation_risk`: `low`, `medium`, `high`.
- `end_state_significance`: `low`, `medium`, `high`.

### approval

- `status`: `draft`, `changes_requested`, or `approved`.
- `gate`: `director_confirmation_required` until approval.
- `open_decisions`.

### image_generation_manifest (legacy v1 only)

This object is the fixed production queue consumed by Storyboard QC:

```json
{
  "manifest_version": "1.0",
  "review_mode": "strict_serial_human_in_the_loop",
  "summary": {
    "character_anchor": 1,
    "group_or_creature_anchor": 0,
    "location_anchor": 1,
    "prop_anchor": 0,
    "shot_start_frame": 1,
    "shot_end_frame": 1,
    "total_visual_requirements": 4,
    "minimum_new_generations": 2,
    "maximum_new_generations": 4
  },
  "queue": [
    {
      "image_id": "IMG_CHAR_001",
      "category": "character_anchor",
      "title": "Primary character identity anchor",
      "purpose": "Lock identity and costume",
      "required": true,
      "priority": "primary",
      "director_asset_ids": ["CHAR_PROTAGONIST_01"],
      "director_state_ids": ["STATE_CHAR_PROTAGONIST_ADULT"],
      "shot_id": null,
      "dependencies": [],
      "must_show": [],
      "must_not_show": [],
      "design_decisions_required": [],
      "allowed_fulfillment_modes": [
        "use_existing_reference",
        "generate_from_reference",
        "generate_new"
      ],
      "fulfillment_mode": "unselected",
      "reference_requirements": {
        "accepted_views": ["front", "side", "back", "three-quarter"],
        "minimum_required_views": 1,
        "coverage_notes": ["face", "silhouette", "costume"]
      },
      "planned_output_path": "visual-assets/anchors/characters/IMG_CHAR_001_v01.png",
      "human_status": "pending"
    }
  ]
}
```

Allowed categories are `character_anchor`, `group_or_creature_anchor`, `location_anchor`, `prop_anchor`, `shot_start_frame`, and `shot_end_frame`. Allowed priorities are `primary`, `secondary`, and `optional`; every item needed for the approved film uses `required: true`. Director delivery always uses `human_status: pending`.

Anchor requirements permit one or more of:

- `use_existing_reference`: review and adopt the user's supplied image without generating a replacement;
- `generate_from_reference`: use supplied images, such as a character turnaround, to create a normalized anchor or state variant;
- `generate_new`: create the anchor from the approved text design.

Anchor `fulfillment_mode` remains `unselected` until Storyboard Gate A. Start and End Frames use only `generate`. A supplied three-view sheet may fulfill a character anchor directly when it covers identity, silhouette, costume, and the relevant state; otherwise use it as the parent reference for generated variants.

There must be exactly one required `shot_start_frame` per Director shot. `shot_end_frame` items are selective but, once included and approved with the Director package, are required unless a later Director revision removes them. Dependencies must point only to earlier manifest items so the queue can run serially.

## Invariants

- Story approval is `approved` before directing begins.
- Scene, asset, state, blocking, action, and shot IDs are unique.
- Every scene has exactly one blocking record and at least one shot.
- Every `must_be_visible` action is covered by at least one shot.
- Every referenced scene, action, character, location, and prop exists.
- Shot durations sum exactly to each scene duration and to the project target.
- The default shot budget is 5–10 seconds per generated shot with a 6–8 second target average; count bounds are derived from total duration.
- Any shot outside 5–10 seconds has a specific entry in `duration_exceptions` and explicit user approval.
- Every shot has one primary causal chain. Up to four tightly coupled action units may share a 5–10 second generated shot; more than two requires an explicit `action_chain_rationale`.
- An axis crossing requires a documented reset.
- For legacy v1 only, every shot has exactly one required Start Frame item in the image manifest.
- For legacy v1 only, manifest IDs are unique, references and dependencies resolve backward, category counts match required items, and each item begins pending with a versioned planned output path.
- Provider prompts and generated asset URLs do not belong in this package.

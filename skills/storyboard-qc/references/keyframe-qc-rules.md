# Keyframe Planning and QC Rules

## Manifest authority

The Image Asset Prompts package supplies the fixed Start and End Frame IDs for new projects; legacy Director v1 manifests also remain valid. Storyboard QC expands their specifications and validates them; it does not add or remove required frames. A wrong frame decision returns to the image plan or Director upstream.

## Start frame

Every shot receives a Start Frame specification containing:

- shot and frame IDs;
- approved anchor references;
- location and state IDs;
- subject ordering, facing, pose, and eyeline;
- required props and their state;
- camera fields inherited from the Shot List;
- visible starting state;
- lighting and time state;
- negative continuity constraints.

The frame should describe a still moment immediately before the primary action becomes ambiguous. Do not depict several phases of motion in one frame.

## End frame decision

Use `start_only` unless a distinct end state materially improves action control or continuity. Use `start_and_end` when at least one applies:

- a handoff or object-state transition completes;
- the subject ends in a materially different location, orientation, height, or pose;
- a magical, healing, damage, weather, or material change must be exact;
- the following shot inherits the resulting composition or state;
- the action has medium or high generation risk and an unconstrained ending would likely drift.

Do not add an End Frame for a simple hold, subtle expression, uncomplicated walk with no precise destination, or atmospheric insert.

## Frame continuity

Across adjacent frames verify:

- identity and age state;
- wardrobe and carried items;
- subject order and screen direction;
- axis side and gaze direction;
- location landmarks and camera side;
- prop ownership, hand, condition, and placement;
- light direction, time, weather, occupancy, and damage state;
- start state equals the preceding required end state when a direct match is intended.

## Per-frame human review

Generate and review exactly one frame at a time. A frame may advance only through an explicit human decision tied to its exact attempt ID. `retry_requested` keeps the old version and names one defect plus the continuity invariants to preserve. Approved frames are frozen.

## Storyboard Contact Sheet

Review frames in final shot order. Mark each frame:

- `approved`;
- `retry_identity`;
- `retry_continuity`;
- `retry_composition`;
- `retry_state`;
- `retry_quality`;
- `discarded`.

Use these labels as QC diagnoses, but record the user-facing decision as `approved`, `retry_requested`, or `rejected`. The Contact Sheet cannot batch-approve frames. Keep approved frames fixed. A retry instruction must name the invariant to preserve and the single defect to correct. Do not regenerate the whole storyboard because a subset failed.

## Prompt boundary

Frame specifications may contain model-neutral visual descriptions. Provider-specific video prompt compilation belongs to Generation Planner. Image-generation adapters may translate a frame specification only during an explicitly authorized image-generation phase.

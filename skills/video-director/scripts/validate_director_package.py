#!/usr/bin/env python3
"""Validate a Video Director package using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


TOP_LEVEL = {
    "schema_version", "project", "source_package", "director_constraints",
    "scenes", "assets", "world_states", "blocking", "shots",
    "image_generation_manifest", "approval",
}

IMAGE_CATEGORIES = {
    "character_anchor", "group_or_creature_anchor", "location_anchor",
    "prop_anchor", "shot_start_frame", "shot_end_frame",
}


def duplicate_values(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def sample_package() -> dict:
    return {
        "schema_version": "1.0",
        "project": {"title": "Test", "language": "en", "output_folder": "."},
        "source_package": {
            "locked_input_file": "02_locked_screenplay_input.json",
            "screenplay_file": "03_video_screenplay.md",
            "story_qc_file": "04_story_qc.md",
            "story_approval_status": "approved",
            "inherited_fidelity_constraints": [],
        },
        "director_constraints": {
            "target_duration_seconds": 6,
            "cost_policy": "one clear action per shot",
            "axis_policy": "preserve axis",
            "action_load_policy": "one primary action",
            "prompt_generation_allowed": False,
            "assumptions": [],
            "shot_budget": {
                "min_shot_duration_seconds": 5,
                "max_shot_duration_seconds": 10,
                "target_average_min_seconds": 6,
                "target_average_max_seconds": 8,
                "shot_count_min": 1,
                "shot_count_max": 1,
                "proposed_count": 1,
                "average_duration_seconds": 6,
                "duration_exceptions": [],
                "exceptions_explicitly_user_approved": False,
                "merge_rationale": [],
            },
        },
        "scenes": [{
            "scene_id": "S01", "title": "Choice", "beat_ids": ["B01"],
            "duration_seconds": 6, "location_ids": ["LOC_ROOM_01"],
            "character_ids": ["CHAR_PERSON_01"], "time_state": "day",
        }],
        "assets": {
            "characters": [{
                "asset_id": "CHAR_PERSON_01", "name": "Person", "role": "protagonist",
                "identity_anchors": [], "design_choices_pending": ["appearance"],
                "allowed_variations": ["pose"], "forbidden_variations": ["identity drift"],
                "states": [{
                    "state_id": "STATE_CHAR_PERSON_01", "scene_ids": ["S01"],
                    "age_phase": "adult", "wardrobe": "design_choice_pending",
                    "condition": [], "carried_prop_ids": [],
                    "emotional_baseline": "uncertain", "continuity_notes": [],
                }],
                "reference_priority": "primary",
            }],
            "locations": [{
                "asset_id": "LOC_ROOM_01", "name": "Room", "scene_ids": ["S01"],
                "fixed_layout": ["door north"], "entrances_exits": ["north door"],
                "landmarks": ["table center"],
                "states": [{
                    "state_id": "STATE_LOC_ROOM_01", "scene_ids": ["S01"],
                    "time": "day", "weather": "not_applicable", "occupancy": "one",
                    "condition": ["orderly"], "lighting_notes": ["daylight"],
                    "continuity_notes": [],
                }],
                "allowed_variations": [], "forbidden_variations": ["layout drift"],
                "reference_priority": "primary",
            }],
            "props": [{
                "asset_id": "PROP_OBJECT_01", "name": "Object", "owner_or_home": "table",
                "scene_ids": ["S01"], "identity_anchors": [],
                "states": ["on table", "held"],
                "state_transitions": ["ACT_S01_01: on table to held"],
                "reference_priority": "secondary",
            }],
        },
        "world_states": [{
            "state_id": "STATE_WORLD_AFTER_S01", "after_scene_id": "S01",
            "character_states": ["STATE_CHAR_PERSON_01"],
            "location_states": ["STATE_LOC_ROOM_01"], "prop_states": ["PROP_OBJECT_01 held"],
            "facts_carried_forward": ["person holds object"],
        }],
        "blocking": [{
            "blocking_id": "BLK_S01", "scene_id": "S01", "location_id": "LOC_ROOM_01",
            "coordinate_convention": "Door north; table center.",
            "axis": {"description": "person to table", "side_rule": "south side",
                     "reset_allowed": False, "reset_method": "none"},
            "start_positions": ["CHAR_PERSON_01 south of table"],
            "actions": [{
                "action_id": "ACT_S01_01", "performer_ids": ["CHAR_PERSON_01"],
                "action": "Person takes the object.", "target_ids": ["PROP_OBJECT_01"],
                "path": "one step to table", "end_position": "beside table",
                "state_changes": ["PROP_OBJECT_01 becomes held"],
                "complexity": "low", "must_be_visible": True,
            }],
            "end_positions": ["CHAR_PERSON_01 beside table holding PROP_OBJECT_01"],
            "continuity_handoff": ["object remains held"], "spatial_risks": [],
        }],
        "shots": [{
            "shot_id": "SH001", "scene_id": "S01", "action_ids": ["ACT_S01_01"],
            "narrative_purpose": "show the choice", "duration_seconds": 6,
            "shot_size": "medium", "camera_height": "eye level",
            "camera_angle": "neutral", "perspective": "natural",
            "camera_movement": "fixed", "movement_reason": "none",
            "composition": "person and table", "focus": "hand taking object",
            "subject_ids": ["CHAR_PERSON_01"], "location_id": "LOC_ROOM_01",
            "prop_ids": ["PROP_OBJECT_01"], "start_visible_state": "object on table",
            "primary_action": "person takes object", "end_visible_state": "object held",
            "axis_side": "south", "continuity_dependencies": [],
            "motion_complexity": "low", "generation_risk": "low", "risk_notes": [],
            "end_state_significance": "high",
        }],
        "image_generation_manifest": {
            "manifest_version": "1.0",
            "review_mode": "strict_serial_human_in_the_loop",
            "summary": {
                "character_anchor": 1, "group_or_creature_anchor": 0,
                "location_anchor": 1, "prop_anchor": 0,
                "shot_start_frame": 1, "shot_end_frame": 1,
                "total_visual_requirements": 4,
                "minimum_new_generations": 2,
                "maximum_new_generations": 4,
            },
            "queue": [
                {
                    "image_id": "IMG_CHAR_001", "category": "character_anchor",
                    "title": "Person identity", "purpose": "lock identity",
                    "required": True, "priority": "primary",
                    "director_asset_ids": ["CHAR_PERSON_01"],
                    "director_state_ids": ["STATE_CHAR_PERSON_01"],
                    "shot_id": None, "dependencies": [], "must_show": [],
                    "must_not_show": [], "design_decisions_required": ["appearance"],
                    "allowed_fulfillment_modes": ["use_existing_reference", "generate_from_reference", "generate_new"],
                    "fulfillment_mode": "unselected",
                    "reference_requirements": {"accepted_views": ["front", "side", "back"],
                                               "minimum_required_views": 1,
                                               "coverage_notes": ["identity", "costume"]},
                    "planned_output_path": "visual-assets/anchors/characters/IMG_CHAR_001_v01.png",
                    "human_status": "pending",
                },
                {
                    "image_id": "IMG_LOC_001", "category": "location_anchor",
                    "title": "Room layout", "purpose": "lock layout",
                    "required": True, "priority": "primary",
                    "director_asset_ids": ["LOC_ROOM_01"],
                    "director_state_ids": ["STATE_LOC_ROOM_01"],
                    "shot_id": None, "dependencies": [], "must_show": [],
                    "must_not_show": [], "design_decisions_required": [],
                    "allowed_fulfillment_modes": ["use_existing_reference", "generate_from_reference", "generate_new"],
                    "fulfillment_mode": "unselected",
                    "reference_requirements": {"accepted_views": ["layout", "environment_concept"],
                                               "minimum_required_views": 1,
                                               "coverage_notes": ["layout"]},
                    "planned_output_path": "visual-assets/anchors/locations/IMG_LOC_001_v01.png",
                    "human_status": "pending",
                },
                {
                    "image_id": "IMG_SH001_START", "category": "shot_start_frame",
                    "title": "SH001 Start Frame", "purpose": "lock start state",
                    "required": True, "priority": "primary",
                    "director_asset_ids": ["CHAR_PERSON_01", "LOC_ROOM_01", "PROP_OBJECT_01"],
                    "director_state_ids": ["STATE_CHAR_PERSON_01", "STATE_LOC_ROOM_01"],
                    "shot_id": "SH001", "dependencies": ["IMG_CHAR_001", "IMG_LOC_001"],
                    "must_show": ["object on table"], "must_not_show": ["object held"],
                    "design_decisions_required": [],
                    "allowed_fulfillment_modes": ["generate"],
                    "fulfillment_mode": "generate",
                    "reference_requirements": {"accepted_views": [], "minimum_required_views": 0,
                                               "coverage_notes": []},
                    "planned_output_path": "visual-assets/keyframes/start/IMG_SH001_START_v01.png",
                    "human_status": "pending",
                },
                {
                    "image_id": "IMG_SH001_END", "category": "shot_end_frame",
                    "title": "SH001 End Frame", "purpose": "lock handoff end state",
                    "required": True, "priority": "primary",
                    "director_asset_ids": ["CHAR_PERSON_01", "LOC_ROOM_01", "PROP_OBJECT_01"],
                    "director_state_ids": ["STATE_CHAR_PERSON_01", "STATE_LOC_ROOM_01"],
                    "shot_id": "SH001", "dependencies": ["IMG_SH001_START"],
                    "must_show": ["object held"], "must_not_show": ["object on table"],
                    "design_decisions_required": [],
                    "allowed_fulfillment_modes": ["generate"],
                    "fulfillment_mode": "generate",
                    "reference_requirements": {"accepted_views": [], "minimum_required_views": 0,
                                               "coverage_notes": []},
                    "planned_output_path": "visual-assets/keyframes/end/IMG_SH001_END_v01.png",
                    "human_status": "pending",
                },
            ],
        },
        "approval": {"status": "draft", "gate": "director_confirmation_required",
                     "open_decisions": []},
    }


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    version = data.get("schema_version")
    if version not in {"1.0", "2.0"}:
        return ["Unsupported Director schema_version"]
    required = TOP_LEVEL - {"image_generation_manifest"} if version == "2.0" else TOP_LEVEL
    missing = required - data.keys()
    if missing:
        return [f"Missing top-level fields: {', '.join(sorted(missing))}"]

    if data["source_package"].get("story_approval_status") != "approved":
        errors.append("source_package.story_approval_status must be approved")
    constraints = data["director_constraints"]
    if constraints.get("prompt_generation_allowed") is not False:
        errors.append("prompt_generation_allowed must be false")
    target_duration = constraints.get("target_duration_seconds")
    if not isinstance(target_duration, int) or target_duration <= 0:
        errors.append("target_duration_seconds must be a positive integer")
    budget = constraints.get("shot_budget", {})
    min_duration = budget.get("min_shot_duration_seconds")
    max_duration = budget.get("max_shot_duration_seconds")
    if min_duration != 5 or max_duration != 10:
        errors.append("Default shot budget must use 5-10 second generated shots")
    if budget.get("target_average_min_seconds") != 6 or budget.get("target_average_max_seconds") != 8:
        errors.append("Default target average must be 6-8 seconds")
    if isinstance(target_duration, int) and min_duration == 5 and max_duration == 10:
        computed_min = math.ceil(target_duration / max_duration)
        computed_max = math.floor(target_duration / min_duration)
        if budget.get("shot_count_min") != computed_min or budget.get("shot_count_max") != computed_max:
            errors.append("shot_budget count bounds do not match total duration and 5-10 second rule")
    if budget.get("proposed_count") != len(data["shots"]):
        errors.append("shot_budget.proposed_count must match shots")
    if (isinstance(budget.get("shot_count_min"), int)
            and isinstance(budget.get("shot_count_max"), int)
            and not budget.get("exceptions_explicitly_user_approved")
            and not budget["shot_count_min"] <= len(data["shots"]) <= budget["shot_count_max"]):
        errors.append("Proposed shot count is outside the duration-derived budget without user approval")
    if isinstance(target_duration, int) and data["shots"]:
        expected_average = target_duration / len(data["shots"])
        if abs(budget.get("average_duration_seconds", -1) - expected_average) > 0.05:
            errors.append("shot_budget.average_duration_seconds does not match duration/shot count")

    scenes = data["scenes"]
    scene_ids = [scene.get("scene_id") for scene in scenes]
    duplicates = duplicate_values([value for value in scene_ids if isinstance(value, str)])
    if duplicates:
        errors.append(f"Duplicate scene IDs: {', '.join(duplicates)}")
    known_scenes = {value for value in scene_ids if isinstance(value, str)}
    scene_duration = {}
    for index, scene in enumerate(scenes, 1):
        duration = scene.get("duration_seconds")
        if not isinstance(duration, int) or duration <= 0:
            errors.append(f"Scene {index} duration must be a positive integer")
        else:
            scene_duration[scene.get("scene_id")] = duration

    assets = data["assets"]
    for key in ("characters", "locations", "props"):
        if key not in assets or not isinstance(assets[key], list):
            errors.append(f"assets.{key} must be an array")
    character_ids = {item.get("asset_id") for item in assets.get("characters", [])}
    location_ids = {item.get("asset_id") for item in assets.get("locations", [])}
    prop_ids = {item.get("asset_id") for item in assets.get("props", [])}
    all_asset_ids = [value for value in character_ids | location_ids | prop_ids if isinstance(value, str)]
    duplicates = duplicate_values(all_asset_ids)
    if duplicates:
        errors.append(f"Duplicate asset IDs: {', '.join(duplicates)}")

    for scene in scenes:
        unknown_characters = set(scene.get("character_ids", [])) - character_ids
        unknown_locations = set(scene.get("location_ids", [])) - location_ids
        if unknown_characters:
            errors.append(f"{scene.get('scene_id')} references unknown characters: {', '.join(sorted(unknown_characters))}")
        if unknown_locations:
            errors.append(f"{scene.get('scene_id')} references unknown locations: {', '.join(sorted(unknown_locations))}")

    blocking_by_scene: dict[str, list[dict]] = defaultdict(list)
    action_ids: set[str] = set()
    visible_actions: set[str] = set()
    reset_allowed: dict[str, bool] = {}
    for block in data["blocking"]:
        scene_id = block.get("scene_id")
        blocking_by_scene[scene_id].append(block)
        if scene_id not in known_scenes:
            errors.append(f"{block.get('blocking_id')} references unknown scene {scene_id}")
        if block.get("location_id") not in location_ids:
            errors.append(f"{block.get('blocking_id')} references unknown location")
        reset_allowed[scene_id] = bool(block.get("axis", {}).get("reset_allowed"))
        for action in block.get("actions", []):
            action_id = action.get("action_id")
            if action_id in action_ids:
                errors.append(f"Duplicate action ID: {action_id}")
            action_ids.add(action_id)
            if action.get("must_be_visible") is True:
                visible_actions.add(action_id)
            if action.get("complexity") not in {"low", "medium", "high"}:
                errors.append(f"{action_id} has invalid complexity")
            unknown_performers = set(action.get("performer_ids", [])) - character_ids
            unknown_targets = set(action.get("target_ids", [])) - (character_ids | location_ids | prop_ids)
            if unknown_performers:
                errors.append(f"{action_id} has unknown performers: {', '.join(sorted(unknown_performers))}")
            if unknown_targets:
                errors.append(f"{action_id} has unknown targets: {', '.join(sorted(unknown_targets))}")

    for scene_id in known_scenes:
        if len(blocking_by_scene[scene_id]) != 1:
            errors.append(f"{scene_id} must have exactly one blocking record")

    shot_ids: list[str] = []
    shots_by_scene: dict[str, list[dict]] = defaultdict(list)
    covered_actions: set[str] = set()
    axis_sides: dict[str, set[str]] = defaultdict(set)
    for shot in data["shots"]:
        shot_id = shot.get("shot_id")
        shot_ids.append(shot_id)
        scene_id = shot.get("scene_id")
        shots_by_scene[scene_id].append(shot)
        if scene_id not in known_scenes:
            errors.append(f"{shot_id} references unknown scene {scene_id}")
        references = shot.get("action_ids", [])
        if len(references) > 4:
            errors.append(f"{shot_id} covers more than four action units")
        if len(references) > 2 and not shot.get("action_chain_rationale"):
            errors.append(f"{shot_id} covers more than two action units without action_chain_rationale")
        unknown_actions = set(references) - action_ids
        if unknown_actions:
            errors.append(f"{shot_id} references unknown actions: {', '.join(sorted(unknown_actions))}")
        covered_actions.update(references)
        if shot.get("location_id") not in location_ids:
            errors.append(f"{shot_id} references unknown location")
        unknown_subjects = set(shot.get("subject_ids", [])) - character_ids
        unknown_props = set(shot.get("prop_ids", [])) - prop_ids
        if unknown_subjects:
            errors.append(f"{shot_id} has unknown subjects: {', '.join(sorted(unknown_subjects))}")
        if unknown_props:
            errors.append(f"{shot_id} has unknown props: {', '.join(sorted(unknown_props))}")
        if shot.get("motion_complexity") not in {"low", "medium", "high"}:
            errors.append(f"{shot_id} has invalid motion_complexity")
        if shot.get("generation_risk") not in {"low", "medium", "high"}:
            errors.append(f"{shot_id} has invalid generation_risk")
        if shot.get("end_state_significance") not in {"low", "medium", "high"}:
            errors.append(f"{shot_id} has invalid end_state_significance")
        duration = shot.get("duration_seconds")
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append(f"{shot_id} duration must be positive")
        side = shot.get("axis_side")
        if side not in {None, "neutral", "on_axis", "not_applicable"}:
            axis_sides[scene_id].add(side)

    exceptions = budget.get("duration_exceptions", [])
    exception_ids = {item.get("shot_id") for item in exceptions if isinstance(item, dict)}
    for shot in data["shots"]:
        duration = shot.get("duration_seconds")
        if isinstance(duration, (int, float)) and not 5 <= duration <= 10:
            if shot.get("shot_id") not in exception_ids:
                errors.append(f"{shot.get('shot_id')} is outside 5-10 seconds without a duration exception")
    for exception in exceptions:
        if exception.get("shot_id") not in set(shot_ids):
            errors.append(f"Duration exception references unknown shot {exception.get('shot_id')}")
        if not exception.get("reason"):
            errors.append(f"Duration exception {exception.get('shot_id')} lacks a reason")
    if exceptions and budget.get("exceptions_explicitly_user_approved") is not True:
        errors.append("Duration exceptions require explicit user approval")

    duplicates = duplicate_values([value for value in shot_ids if isinstance(value, str)])
    if duplicates:
        errors.append(f"Duplicate shot IDs: {', '.join(duplicates)}")
    uncovered = visible_actions - covered_actions
    if uncovered:
        errors.append(f"Visible actions not covered by shots: {', '.join(sorted(uncovered))}")

    total_shot_duration = 0
    for scene_id in known_scenes:
        scene_shots = shots_by_scene[scene_id]
        if not scene_shots:
            errors.append(f"{scene_id} has no shots")
            continue
        duration = sum(shot.get("duration_seconds", 0) for shot in scene_shots
                       if isinstance(shot.get("duration_seconds"), (int, float)))
        total_shot_duration += duration
        if scene_duration.get(scene_id) != duration:
            errors.append(f"{scene_id} shot duration {duration}s does not equal scene duration {scene_duration.get(scene_id)}s")
        if len(axis_sides[scene_id]) > 1 and not reset_allowed.get(scene_id, False):
            errors.append(f"{scene_id} crosses the axis without a documented reset")
    if isinstance(target_duration, int) and total_shot_duration != target_duration:
        errors.append(f"Total shot duration {total_shot_duration}s does not equal target {target_duration}s")

    if version == "2.0":
        if "image_generation_manifest" in data:
            errors.append("v2 Director package must hand image planning to Image Asset Prompts")
        approval = data["approval"]
        if approval.get("status") not in {"draft", "changes_requested", "approved"}:
            errors.append("approval.status is invalid")
        if (approval.get("status") != "approved"
                and approval.get("gate") != "director_confirmation_required"):
            errors.append("Unapproved packages require director_confirmation_required gate")
        return errors

    manifest = data["image_generation_manifest"]
    if manifest.get("review_mode") != "strict_serial_human_in_the_loop":
        errors.append("image_generation_manifest.review_mode must be strict_serial_human_in_the_loop")
    queue = manifest.get("queue")
    if not isinstance(queue, list):
        errors.append("image_generation_manifest.queue must be an array")
        queue = []
    image_ids = [item.get("image_id") for item in queue]
    duplicates = duplicate_values([value for value in image_ids if isinstance(value, str)])
    if duplicates:
        errors.append(f"Duplicate image IDs: {', '.join(duplicates)}")
    known_images: set[str] = set()
    start_frames: dict[str, int] = defaultdict(int)
    category_counts: Counter[str] = Counter()
    all_assets = character_ids | location_ids | prop_ids
    all_states: set[str] = set()
    for group in ("characters", "locations"):
        for asset in assets.get(group, []):
            for state in asset.get("states", []):
                if isinstance(state, dict) and isinstance(state.get("state_id"), str):
                    all_states.add(state["state_id"])
    for item in queue:
        image_id = item.get("image_id")
        category = item.get("category")
        if category not in IMAGE_CATEGORIES:
            errors.append(f"{image_id} has invalid image category")
        if item.get("priority") not in {"primary", "secondary", "optional"}:
            errors.append(f"{image_id} has invalid priority")
        if item.get("required") is not True:
            errors.append(f"{image_id} must be required in an approved Director manifest")
        if item.get("human_status") != "pending":
            errors.append(f"{image_id} must begin with human_status pending")
        modes = item.get("allowed_fulfillment_modes", [])
        fulfillment = item.get("fulfillment_mode")
        if category in {"character_anchor", "group_or_creature_anchor", "location_anchor", "prop_anchor"}:
            allowed_anchor_modes = {"use_existing_reference", "generate_from_reference", "generate_new"}
            if not modes or set(modes) - allowed_anchor_modes:
                errors.append(f"{image_id} has invalid anchor fulfillment modes")
            if fulfillment != "unselected":
                errors.append(f"{image_id} anchor fulfillment_mode must begin unselected")
            if not isinstance(item.get("reference_requirements"), dict):
                errors.append(f"{image_id} lacks reference_requirements")
        else:
            if modes != ["generate"] or fulfillment != "generate":
                errors.append(f"{image_id} shot frame must use generate fulfillment mode")
        if "_v01." not in item.get("planned_output_path", ""):
            errors.append(f"{image_id} planned_output_path must be versioned with _v01")
        unknown_dependencies = set(item.get("dependencies", [])) - known_images
        if unknown_dependencies:
            errors.append(f"{image_id} dependencies must reference earlier queue items: {', '.join(sorted(unknown_dependencies))}")
        unknown_assets = set(item.get("director_asset_ids", [])) - all_assets
        if unknown_assets:
            errors.append(f"{image_id} references unknown Director assets: {', '.join(sorted(unknown_assets))}")
        unknown_states = set(item.get("director_state_ids", [])) - all_states
        if unknown_states:
            errors.append(f"{image_id} references unknown Director states: {', '.join(sorted(unknown_states))}")
        shot_id = item.get("shot_id")
        if category in {"shot_start_frame", "shot_end_frame"}:
            if shot_id not in set(shot_ids):
                errors.append(f"{image_id} references unknown shot {shot_id}")
            if category == "shot_start_frame":
                start_frames[shot_id] += 1
        elif shot_id is not None:
            errors.append(f"{image_id} anchor item must have shot_id null")
        if isinstance(image_id, str):
            known_images.add(image_id)
        if item.get("required") is True and category in IMAGE_CATEGORIES:
            category_counts[category] += 1
    for shot_id in shot_ids:
        if start_frames[shot_id] != 1:
            errors.append(f"{shot_id} must have exactly one required Start Frame manifest item")
    summary = manifest.get("summary", {})
    for category in IMAGE_CATEGORIES:
        if summary.get(category) != category_counts[category]:
            errors.append(f"Manifest summary count mismatch for {category}")
    total_visual = sum(category_counts.values())
    if summary.get("total_visual_requirements") != total_visual:
        errors.append("Manifest summary total_visual_requirements mismatch")
    anchor_count = sum(category_counts[c] for c in {"character_anchor", "group_or_creature_anchor", "location_anchor", "prop_anchor"})
    generated_frame_count = category_counts["shot_start_frame"] + category_counts["shot_end_frame"]
    if summary.get("minimum_new_generations") != generated_frame_count:
        errors.append("Manifest minimum_new_generations must exclude selectable anchors")
    if summary.get("maximum_new_generations") != generated_frame_count + anchor_count:
        errors.append("Manifest maximum_new_generations must include all selectable anchors")

    approval = data["approval"]
    if approval.get("status") not in {"draft", "changes_requested", "approved"}:
        errors.append("approval.status is invalid")
    if (approval.get("status") != "approved"
            and approval.get("gate") != "director_confirmation_required"):
        errors.append("Unapproved packages require director_confirmation_required gate")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        data = sample_package()
    elif args.json_file:
        try:
            data = json.loads(args.json_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    else:
        parser.error("provide json_file or --self-test")
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Director package: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

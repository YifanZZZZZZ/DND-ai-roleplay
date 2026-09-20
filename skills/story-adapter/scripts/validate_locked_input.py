#!/usr/bin/env python3
"""Validate Story Adapter's locked screenplay input using only the stdlib."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOP_LEVEL = {
    "schema_version", "project", "source", "adaptation_constraints",
    "story_core", "motifs", "beats", "screenplay_plan",
    "fidelity_constraints", "unknowns", "approval",
}

BEAT_FIELDS = {
    "beat_id", "title", "start_state", "trigger", "action", "end_state",
    "state_changes", "narrative_function", "characters", "locations",
    "time_marker", "visual_evidence", "treatment", "priority",
    "voiceover_candidates", "must_preserve", "may_compress",
    "must_not_invent", "continuity_facts_created",
}

SCENE_FIELDS = {
    "scene_id", "title", "beat_ids", "dramatic_function", "location", "time",
    "characters", "treatment", "start_visible_state", "end_visible_state",
    "narration_strategy", "target_duration_seconds", "cost_notes",
}


def sample_package() -> dict:
    return {
        "schema_version": "1.0",
        "project": {"title": "Test", "language": "zh-CN", "output_folder": "."},
        "source": {
            "files": ["source.txt"], "source_type": "prose",
            "authorial_perspective": "third_person",
        },
        "adaptation_constraints": {
            "target_duration_seconds": {"min": 8, "max": 12},
            "narration_policy": "sparse", "dialogue_policy": "source_only",
            "cost_policy": "compress repetition", "camera_language_allowed": False,
            "assumptions": [],
        },
        "story_core": {
            "logline": "A person makes a choice.",
            "protagonist_arc": ["uncertain", "decisive"], "theme": "choice",
            "dramatic_question": "Will they choose?", "ending_resolution": "They choose.",
        },
        "motifs": [],
        "beats": [{
            "beat_id": "B01", "title": "Choice", "start_state": "uncertain",
            "trigger": "an opportunity", "action": ["They choose."],
            "end_state": "decisive", "state_changes": ["objective"],
            "narrative_function": "resolve the arc", "characters": ["Protagonist"],
            "locations": ["Room"], "time_marker": "day",
            "visual_evidence": ["They take the object."], "treatment": "must_show",
            "priority": "core", "voiceover_candidates": [],
            "must_preserve": ["choice"], "may_compress": [],
            "must_not_invent": [], "continuity_facts_created": [],
        }],
        "screenplay_plan": [{
            "scene_id": "S01", "title": "Choice", "beat_ids": ["B01"],
            "dramatic_function": "resolve the arc", "location": "Room", "time": "day",
            "characters": ["Protagonist"], "treatment": "scene",
            "start_visible_state": "They hesitate.",
            "end_visible_state": "They leave with the object.",
            "narration_strategy": "none", "target_duration_seconds": 10,
            "cost_notes": [],
        }],
        "fidelity_constraints": {
            "explicit_facts": [], "prohibited_additions": [],
            "adaptation_freedoms": [],
        },
        "unknowns": [],
        "approval": {
            "status": "draft", "gate": "story_confirmation_required",
            "open_decisions": [],
        },
    }


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    missing = TOP_LEVEL - data.keys()
    if missing:
        errors.append(f"Missing top-level fields: {', '.join(sorted(missing))}")
        return errors

    constraints = data["adaptation_constraints"]
    target = constraints.get("target_duration_seconds", {})
    minimum, maximum = target.get("min"), target.get("max")
    if (not isinstance(minimum, int) or not isinstance(maximum, int)
            or minimum <= 0 or maximum < minimum):
        errors.append("target_duration_seconds requires positive integer min/max and max >= min")
    if constraints.get("camera_language_allowed") is not False:
        errors.append("camera_language_allowed must be false")

    beat_ids: list[str] = []
    required_beats: set[str] = set()
    for index, beat in enumerate(data["beats"], 1):
        absent = BEAT_FIELDS - beat.keys()
        if absent:
            errors.append(f"Beat {index} missing fields: {', '.join(sorted(absent))}")
        beat_id = beat.get("beat_id")
        if not isinstance(beat_id, str):
            errors.append(f"Beat {index} has invalid beat_id")
            continue
        beat_ids.append(beat_id)
        if beat.get("priority") in {"core", "required"}:
            required_beats.add(beat_id)
        if beat.get("treatment") not in {
            "must_show", "voiceover_candidate", "montage_candidate", "omit_from_video"
        }:
            errors.append(f"{beat_id} has invalid treatment")
        if beat.get("priority") not in {"core", "required", "optional"}:
            errors.append(f"{beat_id} has invalid priority")

    if len(beat_ids) != len(set(beat_ids)):
        errors.append("Beat IDs must be unique")

    known_beats = set(beat_ids)
    covered_beats: set[str] = set()
    scene_ids: list[str] = []
    duration_total = 0
    for index, scene in enumerate(data["screenplay_plan"], 1):
        absent = SCENE_FIELDS - scene.keys()
        if absent:
            errors.append(f"Scene {index} missing fields: {', '.join(sorted(absent))}")
        scene_id = scene.get("scene_id")
        if isinstance(scene_id, str):
            scene_ids.append(scene_id)
        else:
            errors.append(f"Scene {index} has invalid scene_id")
        references = scene.get("beat_ids", [])
        unknown = set(references) - known_beats
        if unknown:
            errors.append(
                f"{scene_id or f'Scene {index}'} references unknown beats: "
                f"{', '.join(sorted(unknown))}"
            )
        covered_beats.update(references)
        if scene.get("treatment") not in {"scene", "montage", "transition"}:
            errors.append(f"{scene_id or f'Scene {index}'} has invalid treatment")
        duration = scene.get("target_duration_seconds")
        if not isinstance(duration, int) or duration <= 0:
            errors.append(f"{scene_id or f'Scene {index}'} duration must be a positive integer")
        else:
            duration_total += duration

    if len(scene_ids) != len(set(scene_ids)):
        errors.append("Scene IDs must be unique")
    uncovered = required_beats - covered_beats
    if uncovered:
        errors.append(f"Core/required beats not covered: {', '.join(sorted(uncovered))}")
    if (isinstance(minimum, int) and isinstance(maximum, int)
            and not minimum <= duration_total <= maximum):
        errors.append(f"Planned duration {duration_total}s is outside target {minimum}-{maximum}s")

    approval = data["approval"]
    if approval.get("status") not in {"draft", "changes_requested", "approved"}:
        errors.append("approval.status is invalid")
    if (approval.get("status") != "approved"
            and approval.get("gate") != "story_confirmation_required"):
        errors.append("Unapproved packages require the story_confirmation_required gate")
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
    print("Locked screenplay input: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

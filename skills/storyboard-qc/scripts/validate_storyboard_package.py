#!/usr/bin/env python3
"""Validate a strict serial human-in-the-loop Storyboard QC package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


TOP_LEVEL = {
    "schema_version", "project", "source_director_package", "stage",
    "preflight", "visual_design", "reference_sources", "cost_gate", "review_queue", "attempts",
    "human_decisions", "contact_sheets", "approval",
}
STAGES = {"planned", "in_review", "blocked_upstream_revision", "all_items_approved", "approved"}
QUEUE_STATUSES = {
    "pending", "authorized", "generated_waiting_review", "reference_waiting_review", "retry_requested",
    "approved", "rejected", "pending_revalidation",
}
ACTIVE_STATUSES = {"authorized", "generated_waiting_review", "reference_waiting_review", "retry_requested"}
ATTEMPT_STATUSES = {"waiting_human_review", "approved", "superseded", "rejected"}
DECISIONS = {"approved", "retry_requested", "rejected", "approval_revoked"}


def duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def sample_package() -> dict:
    return {
        "schema_version": "2.0",
        "project": {"title": "Test", "output_folder": "."},
        "source_director_package": {
            "file": "", "approval_status": "approved", "manifest_version": "1.0",
            "manifest_item_count": 2,
            "manifest_image_ids": ["IMG_CHAR_001", "IMG_SH001_START"],
            "shot_count": 1, "duration_seconds": 5, "inherited_constraints": [],
        },
        "stage": "planned",
        "preflight": {"status": "passed", "checks": [], "warnings": [],
                      "blocking_issues": [], "upstream_revisions_required": []},
        "visual_design": {"status": "pending", "style": "pending"},
        "reference_sources": [],
        "cost_gate": {"manifest_confirmed": False,
                      "image_generation_authorized": False,
                      "authorized_image_ids": [], "estimated_visual_requirements": 2,
                      "estimated_new_generations_min": 1,
                      "estimated_new_generations_max": 2},
        "review_queue": [
            {"image_id": "IMG_CHAR_001", "category": "character_anchor",
             "required": True, "dependencies": [],
             "planned_output_path": "visual-assets/anchors/characters/IMG_CHAR_001_v01.png",
             "must_show": [], "must_not_show": [],
             "allowed_fulfillment_modes": ["use_existing_reference", "generate_from_reference", "generate_new"],
             "fulfillment_mode": "unselected", "reference_ids": [], "status": "pending",
             "attempt_ids": [], "approved_attempt_id": None},
            {"image_id": "IMG_SH001_START", "category": "shot_start_frame",
             "required": True, "dependencies": ["IMG_CHAR_001"],
             "planned_output_path": "visual-assets/keyframes/start/IMG_SH001_START_v01.png",
             "must_show": [], "must_not_show": [],
             "allowed_fulfillment_modes": ["generate"],
             "fulfillment_mode": "generate", "reference_ids": [], "status": "pending",
             "attempt_ids": [], "approved_attempt_id": None},
        ],
        "attempts": [], "human_decisions": [], "contact_sheets": [],
        "approval": {"status": "draft",
                     "gate": "visual_design_and_manifest_confirmation_required",
                     "current_review_image_id": None, "open_decisions": ["style"]},
    }


def load_director(path_text: str, base: Path) -> tuple[dict | None, str | None]:
    if not path_text:
        return None, None
    path = Path(path_text)
    if not path.is_absolute():
        path = base / path
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Cannot load source Director package: {exc}"


def validate(data: dict, base: Path, check_files: bool = False) -> list[str]:
    errors: list[str] = []
    version = data.get("schema_version")
    if version not in {"2.0", "3.0"}:
        return ["Unsupported Storyboard schema_version"]
    required = TOP_LEVEL | ({"source_image_prompt_package"} if version == "3.0" else set())
    missing = required - data.keys()
    if missing:
        return [f"Missing top-level fields: {', '.join(sorted(missing))}"]
    if data["stage"] not in STAGES:
        errors.append("Invalid stage")

    source = data["source_director_package"]
    if source.get("approval_status") != "approved":
        errors.append("Director package must be approved")
    director, director_error = load_director(source.get("file", ""), base)
    if director_error:
        errors.append(director_error)

    queue = data["review_queue"]
    queue_ids = [item.get("image_id") for item in queue]
    dupe = duplicates([value for value in queue_ids if isinstance(value, str)])
    if dupe:
        errors.append(f"Duplicate queue image IDs: {', '.join(dupe)}")
    if version == "3.0":
        prompt_source = data["source_image_prompt_package"]
        if prompt_source.get("status") != "awaiting_prompt_review":
            errors.append("Prompt package must be awaiting_prompt_review")
        prompt_file = Path(prompt_source.get("file", ""))
        if not prompt_file.is_absolute():
            prompt_file = base / prompt_file
        try:
            prompt_package = json.loads(prompt_file.read_text(encoding="utf-8"))
            prompt_ids = [item.get("image_id") for item in prompt_package.get("items", [])]
            if prompt_package.get("status") != "awaiting_prompt_review":
                errors.append("Source prompt file is not awaiting_prompt_review")
            if queue_ids != prompt_ids:
                errors.append("Review queue does not exactly match image-prompt package")
            if prompt_source.get("item_count") != len(queue):
                errors.append("Prompt item_count does not match review queue")
            if prompt_source.get("source_reference_revision") != prompt_package.get("source_reference_revision"):
                errors.append("Prompt reference revision mismatch")
            intake_file = Path(prompt_package.get("source_intake_file", ""))
            if not intake_file.is_absolute():
                intake_file = base / intake_file
            try:
                intake = json.loads(intake_file.read_text(encoding="utf-8"))
                if intake.get("reference_revision", 0) != prompt_package.get("source_reference_revision"):
                    errors.append("Prompt package is stale relative to intake references")
                relevant = {key: intake.get(key) for key in (
                    "project", "source", "style_brief", "characters", "scenes", "shots",
                    "reference_sources", "reference_revision", "unresolved_design_choices",
                )}
                canonical = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != prompt_package.get("source_intake_sha256"):
                    errors.append("Prompt package is stale relative to intake content")
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"Cannot load source intake file: {exc}")
            for queued, prompted in zip(queue, prompt_package.get("items", [])):
                if queued.get("positive_prompt") != prompted.get("positive_prompt") or queued.get("negative_prompt") != prompted.get("negative_prompt"):
                    errors.append(f"{queued.get('image_id')}: queue prompt differs from source package")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Cannot load source image-prompt package: {exc}")
    else:
        if queue_ids != source.get("manifest_image_ids"):
            errors.append("Review queue order must exactly match source manifest_image_ids")
        if source.get("manifest_item_count") != len(queue):
            errors.append("manifest_item_count does not match review queue")

    if director:
        manifest = director.get("image_generation_manifest", {})
        director_ids = [item.get("image_id") for item in manifest.get("queue", [])]
        if director.get("approval", {}).get("status") != "approved":
            errors.append("Source Director file is not approved")
        if version == "2.0" and queue_ids != director_ids:
            errors.append("Review queue does not exactly match Director manifest")

    gate = data["cost_gate"]
    authorized = gate.get("authorized_image_ids", [])
    if len(authorized) > 1:
        errors.append("At most one image may be authorized at a time")
    if authorized and not gate.get("image_generation_authorized"):
        errors.append("authorized_image_ids requires image_generation_authorized")
    if gate.get("image_generation_authorized") and not gate.get("manifest_confirmed"):
        errors.append("Image generation requires manifest confirmation")
    visual_count = sum(item.get("required") is True for item in queue)
    selectable_anchor_count = sum("generate_new" in item.get("allowed_fulfillment_modes", []) for item in queue)
    required_frame_count = visual_count - selectable_anchor_count
    if gate.get("estimated_visual_requirements") != visual_count:
        errors.append("estimated_visual_requirements does not match required queue items")
    if gate.get("estimated_new_generations_min") != required_frame_count:
        errors.append("estimated_new_generations_min must exclude selectable anchors")
    if gate.get("estimated_new_generations_max") != visual_count:
        errors.append("estimated_new_generations_max must include selectable anchors")

    reference_ids = [item.get("reference_id") for item in data["reference_sources"]]
    dupe = duplicates([value for value in reference_ids if isinstance(value, str)])
    if dupe:
        errors.append(f"Duplicate reference IDs: {', '.join(dupe)}")
    known_references = set(reference_ids)
    for reference in data["reference_sources"]:
        if reference.get("source_type") not in {"three_view_sheet", "turnaround", "portrait", "full_body", "environment_concept", "layout", "prop_sheet"}:
            errors.append(f"{reference.get('reference_id')} has invalid source_type")
        if reference.get("status") not in {"pending_human_review", "approved", "rejected"}:
            errors.append(f"{reference.get('reference_id')} has invalid status")

    known_queue = set(queue_ids)
    active = [item for item in queue if item.get("status") in ACTIVE_STATUSES]
    if len(active) > 1:
        errors.append("At most one queue item may be active or awaiting review")

    seen_unapproved_required = False
    for index, item in enumerate(queue):
        image_id = item.get("image_id")
        status = item.get("status")
        if status not in QUEUE_STATUSES:
            errors.append(f"{image_id} has invalid queue status")
        modes = item.get("allowed_fulfillment_modes", [])
        fulfillment = item.get("fulfillment_mode")
        if fulfillment != "unselected" and fulfillment not in modes:
            errors.append(f"{image_id} fulfillment_mode is not allowed")
        unknown_refs = set(item.get("reference_ids", [])) - known_references
        if unknown_refs:
            errors.append(f"{image_id} references unknown reference sources")
        if fulfillment in {"use_existing_reference", "generate_from_reference"} and not item.get("reference_ids"):
            errors.append(f"{image_id} selected reference mode without reference_ids")
        if fulfillment == "generate" and modes != ["generate"]:
            errors.append(f"{image_id} generated frame has invalid modes")
        unknown_deps = set(item.get("dependencies", [])) - known_queue
        if unknown_deps:
            errors.append(f"{image_id} references unknown dependencies")
        if any(queue_ids.index(dep) >= index for dep in item.get("dependencies", []) if dep in known_queue):
            errors.append(f"{image_id} dependencies must appear earlier in the queue")
        advanced = status not in {"pending", "pending_revalidation"}
        if advanced and seen_unapproved_required:
            errors.append(f"{image_id} advanced before an earlier required item was approved")
        if item.get("required") is True and status != "approved":
            seen_unapproved_required = True
        if advanced:
            dep_status = {q.get("image_id"): q.get("status") for q in queue}
            if any(dep_status.get(dep) != "approved" for dep in item.get("dependencies", [])):
                errors.append(f"{image_id} advanced before all dependencies were approved")
        if status in ACTIVE_STATUSES and authorized != [image_id]:
            errors.append(f"Active item {image_id} must be the sole authorized image")

    attempt_ids = [item.get("attempt_id") for item in data["attempts"]]
    dupe = duplicates([value for value in attempt_ids if isinstance(value, str)])
    if dupe:
        errors.append(f"Duplicate attempt IDs: {', '.join(dupe)}")
    attempts_by_image: dict[str, list[dict]] = defaultdict(list)
    for attempt in data["attempts"]:
        image_id = attempt.get("image_id")
        attempts_by_image[image_id].append(attempt)
        if image_id not in known_queue:
            errors.append(f"Attempt references unknown image {image_id}")
        if attempt.get("status") not in ATTEMPT_STATUSES:
            errors.append(f"{attempt.get('attempt_id')} has invalid attempt status")
        if check_files:
            path = Path(attempt.get("file", ""))
            if not path.is_absolute():
                path = base / path
            if not path.is_file():
                errors.append(f"Generated file is missing: {path}")
    for image_id, attempts in attempts_by_image.items():
        versions = sorted(item.get("version") for item in attempts if isinstance(item.get("version"), int))
        if versions != list(range(1, len(versions) + 1)):
            errors.append(f"{image_id} attempt versions must start at 1 and have no gaps")

    decision_ids = [item.get("decision_id") for item in data["human_decisions"]]
    dupe = duplicates([value for value in decision_ids if isinstance(value, str)])
    if dupe:
        errors.append(f"Duplicate human decision IDs: {', '.join(dupe)}")
    approved_decisions: dict[tuple[str, str], int] = Counter()
    for decision in data["human_decisions"]:
        if decision.get("decision") not in DECISIONS:
            errors.append(f"{decision.get('decision_id')} has invalid decision")
        if decision.get("recorded_from_user") is not True:
            errors.append(f"{decision.get('decision_id')} must be explicitly recorded from the user")
        if decision.get("attempt_id") not in set(attempt_ids):
            errors.append(f"{decision.get('decision_id')} references unknown attempt")
        if decision.get("decision") == "retry_requested":
            if not decision.get("defect") or not decision.get("preserve") or not decision.get("requested_change"):
                errors.append(f"{decision.get('decision_id')} retry lacks defect, preserve, or requested_change")
        if decision.get("decision") == "approved":
            approved_decisions[(decision.get("image_id"), decision.get("attempt_id"))] += 1

    attempt_lookup = {item.get("attempt_id"): item for item in data["attempts"]}
    for item in queue:
        image_id = item.get("image_id")
        if set(item.get("attempt_ids", [])) != {a.get("attempt_id") for a in attempts_by_image.get(image_id, [])}:
            errors.append(f"{image_id} attempt_ids do not match attempt records")
        if item.get("status") == "approved":
            approved_attempt_id = item.get("approved_attempt_id")
            if attempt_lookup.get(approved_attempt_id, {}).get("status") != "approved":
                errors.append(f"{image_id} lacks an approved attempt")
            if approved_decisions[(image_id, approved_attempt_id)] != 1:
                errors.append(f"{image_id} requires exactly one explicit human approval decision")

    if check_files:
        for sheet in data["contact_sheets"]:
            path = Path(sheet.get("file", ""))
            if not path.is_absolute():
                path = base / path
            if not path.is_file():
                errors.append(f"Contact Sheet is missing: {path}")

    current = data["approval"].get("current_review_image_id")
    waiting = [item.get("image_id") for item in queue if item.get("status") == "generated_waiting_review"]
    waiting += [item.get("image_id") for item in queue if item.get("status") == "reference_waiting_review"]
    if current != (waiting[0] if len(waiting) == 1 else None):
        errors.append("current_review_image_id must identify the sole generated_waiting_review item")

    if data["stage"] in {"all_items_approved", "approved"}:
        if any(item.get("required") is True and item.get("status") != "approved" for item in queue):
            errors.append("All required items must be individually approved")
        if active:
            errors.append("No item may remain active after all_items_approved")
    if data["stage"] == "approved":
        if data["approval"].get("status") != "approved" or data["approval"].get("gate") != "storyboard_confirmed":
            errors.append("Approved stage requires final storyboard confirmation")

    allowed_gates = {
        "visual_design_and_manifest_confirmation_required", "image_review_required",
        "upstream_revision_required", "final_sequence_confirmation_required",
        "storyboard_confirmed",
    }
    if data["approval"].get("gate") not in allowed_gates:
        errors.append("approval.gate is invalid")
    if data["approval"].get("status") not in {"draft", "changes_requested", "approved"}:
        errors.append("approval.status is invalid")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        data = sample_package()
        base = Path.cwd()
    elif args.json_file:
        try:
            data = json.loads(args.json_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        base = args.json_file.resolve().parent
    else:
        parser.error("provide json_file or --self-test")
    errors = validate(data, base, args.check_files)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Storyboard package: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

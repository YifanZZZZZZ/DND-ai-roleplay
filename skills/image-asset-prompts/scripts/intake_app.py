#!/usr/bin/env python3
"""Local reference-intake page and deterministic batch image-prompt builder."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import secrets
import sys
import tempfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


CATEGORIES = (
    "person_with_reference", "person_without_reference",
    "scene_with_reference", "scene_without_reference", "shot_frame",
)
GENERIC_NEGATIVE = "低质量，模糊，文字，水印，错误肢体，多余手指"
MAX_UPLOAD = 30 * 1024 * 1024


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".intake-", suffix=".tmp", delete=False) as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temporary = Path(file.name)
    os.replace(temporary, path)


def story_root(path: Path, data: dict) -> Path:
    root = Path(data.get("project", {}).get("story_folder", ""))
    if not root.is_absolute() or root.resolve() != path.resolve().parent.parent:
        raise ValueError("project.story_folder must be the absolute parent of image-prep")
    return root.resolve()


def entities(data: dict) -> list[dict]:
    return data.get("characters", []) + data.get("scenes", [])


def validate_intake(path: Path, data: dict) -> list[str]:
    errors: list[str] = []
    try:
        root = story_root(path, data)
    except ValueError as exc:
        return [str(exc)]
    if path.name != "asset-intake.json" or path.parent.name != "image-prep":
        errors.append("Intake path must be <story-folder>/image-prep/asset-intake.json")
    if data.get("schema_version") != "1.0":
        errors.append("Unsupported intake schema_version")
    if any(key in {"positive_prompt", "negative_prompt"}
           for row in entities(data) + data.get("shots", [])
           for key in row.keys()):
        errors.append("Phase-1 intake must not contain generated prompts")
    for key in ("characters", "scenes", "shots"):
        if not isinstance(data.get(key), list):
            errors.append(f"{key} must be an array")
    if errors:
        return errors
    image_ids = [row.get("image_id") for row in entities(data)]
    if any(not isinstance(value, str) or not value.startswith("IMG_") for value in image_ids):
        errors.append("Each entity needs a stable IMG_* image_id")
    if len(image_ids) != len(set(image_ids)):
        errors.append("Duplicate entity image_id")
    asset_ids = {row.get("asset_id") for row in entities(data)}
    shot_ids = [row.get("shot_id") for row in data["shots"]]
    if len(shot_ids) != len(set(shot_ids)) or not shot_ids:
        errors.append("Shot IDs must be unique and nonempty")
    all_frame_ids: list[str] = []
    for row in entities(data):
        iid = row.get("image_id")
        if not row.get("asset_id") or not row.get("name") or not row.get("brief"):
            errors.append(f"{iid}: asset_id, name and brief are required")
        if not set(row.get("shot_ids", [])) <= set(shot_ids):
            errors.append(f"{iid}: unknown shot in shot_ids")
        if not isinstance(row.get("must_show", []), list) or not isinstance(row.get("must_not_show", []), list):
            errors.append(f"{iid}: must_show/must_not_show must be arrays")
    for shot in data["shots"]:
        sid = shot.get("shot_id")
        if not set(shot.get("anchor_image_ids", [])) <= set(image_ids):
            errors.append(f"{sid}: unknown anchor_image_ids")
        if not set(shot.get("subject_asset_ids", [])) <= asset_ids:
            errors.append(f"{sid}: unknown subject_asset_ids")
        if shot.get("location_asset_id") not in asset_ids:
            errors.append(f"{sid}: unknown location_asset_id")
        start = shot.get("start", {})
        if start.get("image_id") != f"IMG_{sid}_START" or not start.get("brief"):
            errors.append(f"{sid}: one start frame with IMG_{sid}_START and brief is required")
        all_frame_ids.append(start.get("image_id"))
        end = shot.get("end", {})
        if end.get("required"):
            if end.get("image_id") != f"IMG_{sid}_END" or not end.get("brief") or not end.get("reason"):
                errors.append(f"{sid}: required end frame needs ID, brief and reason")
            all_frame_ids.append(end.get("image_id"))
    if len(image_ids + all_frame_ids) != len(set(image_ids + all_frame_ids)):
        errors.append("Duplicate image ID across anchors and frames")
    refs = data.get("reference_sources", {})
    if not isinstance(refs, dict) or not set(refs) <= set(image_ids):
        errors.append("reference_sources must be an object keyed by known anchor image IDs")
    else:
        for iid, files in refs.items():
            if not isinstance(files, list):
                errors.append(f"{iid}: references must be an array")
                continue
            for item in files:
                candidate = (root / item.get("stored_path", "")).resolve()
                expected = (root / "image-prep" / "references" / iid).resolve()
                if not candidate.is_relative_to(expected) or not candidate.is_file():
                    errors.append(f"{iid}: invalid or missing reference file")
    return errors


def sentence(parts: list[str]) -> str:
    return "。".join(str(part).strip(" 。") for part in parts if str(part).strip(" 。")) + "。"


def joined(items: list[str]) -> str:
    return "、".join(str(item) for item in items if str(item).strip())


def intake_fingerprint(data: dict) -> str:
    """Hash prompt-relevant inputs, excluding bookkeeping written after generation."""
    relevant = {key: data.get(key) for key in (
        "project", "source", "style_brief", "characters", "scenes", "shots",
        "reference_sources", "reference_revision", "unresolved_design_choices",
    )}
    canonical = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def anchor_prompt(row: dict, has_ref: bool, style: str, paths: list[str], kind: str) -> tuple[str, str]:
    title = row["name"]
    if kind == "person":
        opening = (f"以所附参考图为{title}的身份特征与画风依据；目标年龄、服装和姿态以本条视觉需求为准，保留指定不变特征，不机械复制参考图中的年龄或衣服"
                   if has_ref else f"根据剧本设定创作{title}的独立角色锚点；不借用其他人物的脸、发型或服装")
        framing = "单一可辨认角色，脸部、发型、服装轮廓清楚，背景简洁"
        negative = "第二个人，多人拼贴，三视图拼贴，目标年龄错误，目标服装错误，复制其他角色的面容"
    else:
        opening = (f"以所附参考图为{title}的布局、建筑或道具外观依据；保持可识别结构"
                   if has_ref else f"根据剧本与世界空间规划创建{title}的场景或关键道具锚点")
        framing = "空间方向、入口出口、固定地标和光照状态明确；不加入无依据的人物"
        negative = "空间轴线颠倒，入口位置变化，无关人物，布局不连续"
    positive = sentence([opening,
                         f"参考文件：{joined(paths)}" if paths else "",
                         row["brief"], f"统一画风：{style}",
                         f"必须呈现：{joined(row.get('must_show', []))}" if row.get("must_show") else "",
                         f"用户补充：{row.get('user_notes', '')}" if row.get("user_notes") else "",
                         f"画幅 {row.get('aspect_ratio', '由镜头决定')}；{framing}"])
    negative_prompt = sentence([GENERIC_NEGATIVE, negative,
                                joined(row.get("must_not_show", []))])
    return positive, negative_prompt


def frame_prompt(shot: dict, state: dict, is_end: bool, anchors: list[dict], style: str) -> tuple[str, str]:
    sid = shot["shot_id"]
    anchor_names = joined([f"{row['image_id']}（{row['name']}）" for row in anchors])
    if is_end:
        opening = f"生成 {sid} 的结束帧；必须承接同镜头起始帧及相同角色、服装、场景布局和轴线"
        temporal = f"动作完成后的状态：{state['brief']}；结束帧理由：{shot['end']['reason']}"
    else:
        opening = f"生成 {sid} 的视频起始帧；这是动作开始前的一张静止画面，不要提前出现完成状态"
        temporal = f"画面初态：{state['brief']}；随后将发生的动作仅供理解，不画其结果：{shot.get('action', '')}"
    positive = sentence([opening, f"沿用已确定锚点：{anchor_names}",
                         f"景别、机位与构图：{shot.get('camera', '')}", temporal,
                         f"统一画风：{style}",
                         f"必须呈现：{joined(state.get('must_show', []))}" if state.get("must_show") else "",
                         f"画幅 {state.get('aspect_ratio', '由导演包决定')}"])
    negative = sentence([GENERIC_NEGATIVE, "人物身份变化，服装漂移，场景布局变化，错误人数，错误道具数量",
                         joined(state.get("must_not_show", []))])
    return positive, negative


def build_package(path: Path, data: dict) -> dict:
    errors = validate_intake(path, data)
    if errors:
        raise ValueError("; ".join(errors))
    style = data.get("style_brief", "")
    refs = data.get("reference_sources", {})
    items: list[dict] = []
    anchor_by_id = {row["image_id"]: row for row in entities(data)}
    counts: Counter[str] = Counter()
    for kind, rows in (("person", data["characters"]), ("scene", data["scenes"])):
        for row in rows:
            paths = [item["stored_path"] for item in refs.get(row["image_id"], [])]
            category = f"{kind}_{'with' if paths else 'without'}_reference"
            positive, negative = anchor_prompt(row, bool(paths), style, paths, kind)
            items.append({"image_id": row["image_id"], "category": category,
                          "asset_subtype": row.get("asset_subtype", kind),
                          "asset_ids": [row["asset_id"]], "state_ids": row.get("state_ids", []),
                          "shot_id": None, "dependencies": [], "reference_paths": paths,
                          "must_show": row.get("must_show", []), "must_not_show": row.get("must_not_show", []),
                          "aspect_ratio": row.get("aspect_ratio", ""), "positive_prompt": positive,
                          "negative_prompt": negative, "human_status": "pending"})
            counts[category] += 1
    for shot in data["shots"]:
        anchor_ids = shot["anchor_image_ids"]
        anchors = [anchor_by_id[iid] for iid in anchor_ids]
        ref_paths = [ref["stored_path"] for iid in anchor_ids for ref in refs.get(iid, [])]
        for is_end, state in ((False, shot["start"]), (True, shot.get("end", {}))):
            if is_end and not state.get("required"):
                continue
            positive, negative = frame_prompt(shot, state, is_end, anchors, style)
            items.append({"image_id": state["image_id"], "category": "shot_frame",
                          "asset_subtype": "end_frame" if is_end else "start_frame",
                          "asset_ids": shot.get("subject_asset_ids", []) + [shot["location_asset_id"]]
                          + shot.get("support_asset_ids", []), "state_ids": [],
                          "shot_id": shot["shot_id"],
                          "dependencies": [shot["start"]["image_id"]] if is_end else anchor_ids,
                          "reference_paths": ref_paths, "must_show": state.get("must_show", []),
                          "must_not_show": state.get("must_not_show", []),
                          "aspect_ratio": state.get("aspect_ratio", ""),
                          "positive_prompt": positive, "negative_prompt": negative,
                          "human_status": "pending"})
            counts["shot_frame"] += 1
    approved = (data.get("source", {}).get("story_approval_status") == "approved"
                and data.get("source", {}).get("director_approval_status") == "approved"
                and not data.get("unresolved_design_choices"))
    return {"schema_version": "1.0", "status": "awaiting_prompt_review" if approved else "draft_review",
            "source_intake_file": "image-prep/asset-intake.json",
            "source_reference_revision": data.get("reference_revision", 0),
            "source_intake_sha256": intake_fingerprint(data),
            "source_director_package_file": data.get("source", {}).get("director_package_file", ""),
            "categories": {key: counts[key] for key in CATEGORIES}, "items": items}


def validate_package(package: dict, intake: dict) -> list[str]:
    errors: list[str] = []
    items = package.get("items", [])
    ids = [item.get("image_id") for item in items]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate prompt image IDs")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    for item in items:
        iid = item.get("image_id")
        cat = item.get("category")
        if cat not in CATEGORIES or not item.get("positive_prompt") or not item.get("negative_prompt"):
            errors.append(f"{iid}: invalid category or empty prompt")
        if not set(item.get("dependencies", [])) <= seen:
            errors.append(f"{iid}: dependency not earlier")
        if item.get("human_status") != "pending":
            errors.append(f"{iid}: human_status must be pending")
        counts[cat] += 1
        seen.add(iid)
    if package.get("categories") != {key: counts[key] for key in CATEGORIES}:
        errors.append("Category counts do not match items")
    if package.get("source_reference_revision") != intake.get("reference_revision", 0):
        errors.append("Prompt package is stale relative to reference selection")
    if package.get("source_intake_sha256") != intake_fingerprint(intake):
        errors.append("Prompt package is stale relative to intake content")
    if counts["shot_frame"] != len(intake["shots"]) + sum(bool(s.get("end", {}).get("required")) for s in intake["shots"]):
        errors.append("Shot-frame count does not match required Start/End Frames")
    return errors


def write_markdown(package: dict) -> str:
    labels = {"person_with_reference": "有素材人物", "person_without_reference": "无素材人物",
              "scene_with_reference": "有素材场景", "scene_without_reference": "无素材场景",
              "shot_frame": "首尾帧"}
    lines = ["# 图片生成 Prompt 清单", "", f"状态：{package['status']}；仅为文字 Prompt，未生成图片。", ""]
    for category in CATEGORIES:
        lines.extend([f"## {labels[category]}（{package['categories'][category]}）", ""])
        for item in package["items"]:
            if item["category"] != category:
                continue
            lines.extend([f"### {item['image_id']}", "",
                          f"依赖：{joined(item['dependencies']) or '无'}；参考图：{joined(item['reference_paths']) or '无'}", "",
                          "正面 Prompt：", "", item["positive_prompt"], "",
                          "负面 Prompt：", "", item["negative_prompt"], ""])
    return "\n".join(lines)


def generate_files(path: Path, data: dict) -> tuple[Path, Path, dict]:
    package = build_package(path, data)
    errors = validate_package(package, data)
    if errors:
        raise ValueError("; ".join(errors))
    prep = path.parent
    existing = [int(match.group(1)) for candidate in prep.glob("image-prompt-package_v*.json")
                if (match := re.fullmatch(r"image-prompt-package_v(\d+)\.json", candidate.name))]
    version = max(existing, default=0) + 1
    json_path = prep / f"image-prompt-package_v{version:02d}.json"
    markdown_path = prep / f"image-prompts_v{version:02d}.md"
    atomic_json(json_path, package)
    markdown_path.write_text(write_markdown(package), encoding="utf-8")
    data["last_generated_revision"] = data.get("reference_revision", 0)
    data["last_prompt_package"] = json_path.name
    atomic_json(path, data)
    return json_path, markdown_path, package


def image_bytes_ok(payload: bytes) -> bool:
    return payload.startswith(b"\x89PNG\r\n\x1a\n") or payload.startswith(b"\xff\xd8\xff") or payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"


def serve(path: Path, host: str, port: int) -> None:
    intake = load_json(path)
    errors = validate_intake(path, intake)
    if errors:
        raise ValueError("; ".join(errors))
    root = story_root(path, intake)
    template = (Path(__file__).resolve().parent.parent / "assets" / "intake.html").read_text(encoding="utf-8")
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code: int, value: object) -> None:
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def state(self) -> dict:
            data = load_json(path)
            return {"project": data["project"], "characters": data["characters"],
                    "scenes": data["scenes"], "reference_sources": data.get("reference_sources", {}),
                    "reference_revision": data.get("reference_revision", 0),
                    "last_generated_revision": data.get("last_generated_revision"),
                    "last_prompt_package": data.get("last_prompt_package"),
                    "frame_count": len(data["shots"]) + sum(bool(s.get("end", {}).get("required")) for s in data["shots"]),
                    "upstream_approved": data.get("source", {}).get("story_approval_status") == "approved"
                    and data.get("source", {}).get("director_approval_status") == "approved"}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                page = template.replace("__TOKEN__", html.escape(token, quote=True)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            elif parsed.path == "/api/state":
                self.reply(200, self.state())
            elif parsed.path == "/api/ref":
                relative = parse_qs(parsed.query).get("path", [""])[0]
                candidate = (root / relative).resolve()
                allowed = (root / "image-prep" / "references").resolve()
                if not candidate.is_relative_to(allowed) or not candidate.is_file():
                    self.reply(404, {"error": "Reference not found"})
                    return
                payload = candidate.read_bytes()
                mime = "image/png" if candidate.suffix.lower() == ".png" else "image/webp" if candidate.suffix.lower() == ".webp" else "image/jpeg"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
            elif parsed.path.startswith("/download/"):
                name = unquote(parsed.path.rsplit("/", 1)[-1])
                if not re.fullmatch(r"image-(?:prompt-package|prompts)_v\d+\.(?:json|md)", name):
                    self.reply(404, {"error": "Not found"})
                    return
                target = path.parent / name
                if not target.is_file():
                    self.reply(404, {"error": "Not found"})
                    return
                payload = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8" if name.endswith(".json") else "text/markdown; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.reply(404, {"error": "Not found"})

        def do_POST(self) -> None:
            origin = self.headers.get("Origin")
            allowed_origin = f"http://{self.headers.get('Host', '')}"
            if self.headers.get("X-Intake-Token") != token or origin and origin != allowed_origin:
                self.reply(403, {"error": "Invalid page token or origin"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if not 0 < length <= MAX_UPLOAD:
                self.reply(413, {"error": "Invalid size or upload larger than 30 MB"})
                return
            body = self.rfile.read(length)
            parsed = urlparse(self.path)
            data = load_json(path)
            known = {row["image_id"] for row in entities(data)}
            try:
                if parsed.path == "/api/upload":
                    params = parse_qs(parsed.query)
                    iid = params.get("image_id", [""])[0]
                    name = Path(params.get("name", [""])[0]).name
                    if iid not in known or not name or not image_bytes_ok(body):
                        raise ValueError("Choose a valid row and PNG, JPEG, or WEBP image")
                    digest = hashlib.sha256(body).hexdigest()
                    safe = re.sub(r"[^\w.\-]", "_", name)[:100]
                    destination = root / "image-prep" / "references" / iid / f"{digest[:12]}_{safe}"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if not destination.exists():
                        destination.write_bytes(body)
                    entry = {"original_name": name, "stored_path": str(destination.relative_to(root)),
                             "sha256": digest, "size_bytes": len(body)}
                    values = data.setdefault("reference_sources", {}).setdefault(iid, [])
                    if all(value.get("sha256") != digest for value in values):
                        values.append(entry)
                        data["reference_revision"] = data.get("reference_revision", 0) + 1
                elif parsed.path in {"/api/note", "/api/remove", "/api/generate"}:
                    request = json.loads(body.decode("utf-8"))
                    if parsed.path == "/api/generate":
                        if request.get("confirmed") is not True:
                            raise ValueError("Confirm all reference choices first")
                        json_file, md_file, package = generate_files(path, data)
                        self.reply(200, {"json": json_file.name, "markdown": md_file.name,
                                         "status": package["status"], "categories": package["categories"]})
                        return
                    iid = request.get("image_id")
                    if iid not in known:
                        raise ValueError("Unknown image_id")
                    if parsed.path == "/api/note":
                        row = next(row for row in entities(data) if row["image_id"] == iid)
                        note = request.get("note", "")
                        if not isinstance(note, str) or len(note) > 2000:
                            raise ValueError("Note must be under 2000 characters")
                        if row.get("user_notes", "") != note:
                            row["user_notes"] = note
                            data["reference_revision"] = data.get("reference_revision", 0) + 1
                    else:
                        digest = request.get("sha256", "")
                        values = data.setdefault("reference_sources", {}).setdefault(iid, [])
                        new_values = [value for value in values if value.get("sha256") != digest]
                        if len(new_values) != len(values):
                            data["reference_sources"][iid] = new_values
                            data["reference_revision"] = data.get("reference_revision", 0) + 1
                else:
                    self.reply(404, {"error": "Not found"})
                    return
                atomic_json(path, data)
                self.reply(200, self.state())
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.reply(400, {"error": str(exc)})

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Reference intake page: http://{host}:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "generate", "serve"):
        command = sub.add_parser(name)
        command.add_argument("intake", type=Path)
        if name == "serve":
            command.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    path = args.intake.resolve()
    try:
        data = load_json(path)
        errors = validate_intake(path, data)
        if errors:
            raise ValueError("; ".join(errors))
        if args.command == "serve":
            serve(path, "127.0.0.1", args.port)
        elif args.command == "generate":
            json_file, md_file, package = generate_files(path, data)
            print(f"{json_file}\n{md_file}\nstatus={package['status']}")
        else:
            last = data.get("last_prompt_package")
            if last:
                package = load_json(path.parent / last)
                errors = validate_package(package, data)
                if errors:
                    raise ValueError("; ".join(errors))
            print("Image asset intake: OK")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

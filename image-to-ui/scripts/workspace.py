"""Coordinate many single-page Image-To-UI tasks from one workspace manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Page:
    id: str
    project_id: str
    design: Path
    asset_root: Path
    selected_dirs: tuple[str, ...]
    output: Path
    prefab_path: str
    unity_project: Path | None
    functional: dict[str, Any]
    view: Path
    known_pages: tuple[str, ...]


@dataclass(frozen=True)
class Project:
    id: str
    asset_root: Path
    unity_project: Path | None
    pages: tuple[Page, ...]


@dataclass(frozen=True)
class Workspace:
    manifest: Path
    projects: tuple[Project, ...]


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkspaceError(f"{label} must be an object")
    return value


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) is None:
        raise WorkspaceError(f"{label} must be a simple ID containing letters, digits, '-' or '_'")
    return value


def _path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceError(f"{label} must be a nonempty path")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def _within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _asset_dirs(asset_root: Path, value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise WorkspaceError(f"{label} must be a list of relative directories")
    result: list[str] = []
    for raw in value:
        rel = Path(raw)
        if not raw or rel.is_absolute() or any(part in (".", "..") for part in rel.parts):
            raise WorkspaceError(f"{label} must contain only safe relative directories: {raw!r}")
        full = (asset_root / rel).resolve()
        if not _within(full, asset_root) or not full.is_dir():
            raise WorkspaceError(f"{label} directory is missing or escapes assetRoot: {raw!r}")
        normalized = rel.as_posix()
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def load_workspace(path: Path) -> Workspace:
    manifest = path.expanduser().resolve()
    try:
        doc = _object(json.loads(manifest.read_text(encoding="utf-8")), "workspace")
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"Cannot read workspace manifest: {manifest}: {exc}") from exc
    if doc.get("version") != 1:
        raise WorkspaceError("workspace.version must be 1")
    raw_projects = doc.get("projects")
    if not isinstance(raw_projects, list) or not raw_projects:
        raise WorkspaceError("workspace.projects must be a nonempty list")
    projects: list[Project] = []
    project_ids: set[str] = set()
    output_paths: list[Path] = []
    target_paths: set[tuple[str, str]] = set()
    asset_roots: list[Path] = []
    for raw_project in raw_projects:
        item = _object(raw_project, "project")
        project_id = _id(item.get("id"), "project.id")
        if project_id in project_ids:
            raise WorkspaceError(f"duplicate project ID: {project_id}")
        project_ids.add(project_id)
        asset_root = _path(manifest.parent, item.get("assetRoot"), "project.assetRoot")
        if not asset_root.is_dir():
            raise WorkspaceError(f"assetRoot does not exist: {asset_root}")
        asset_roots.append(asset_root)
        unity_project = None
        if item.get("unityProject") is not None:
            unity_project = _path(manifest.parent, item["unityProject"], "project.unityProject")
            if not (unity_project / "Assets").is_dir():
                raise WorkspaceError(f"unityProject lacks Assets/: {unity_project}")
        common = _asset_dirs(asset_root, item.get("commonAssetDirs", []), "commonAssetDirs")
        raw_pages = item.get("pages")
        if not isinstance(raw_pages, list) or not raw_pages:
            raise WorkspaceError(f"project {project_id} pages must be a nonempty list")
        pages: list[Page] = []
        page_ids: set[str] = set()
        known_pages = tuple(_id(_object(raw, "page").get("id"), "page.id") for raw in raw_pages)
        for raw_page in raw_pages:
            page = _object(raw_page, f"project {project_id} page")
            page_id = _id(page.get("id"), "page.id")
            if page_id in page_ids:
                raise WorkspaceError(f"duplicate page ID in {project_id}: {page_id}")
            page_ids.add(page_id)
            design = _path(manifest.parent, page.get("design"), "page.design")
            if not design.is_file() or design.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                raise WorkspaceError(f"design image is missing or unsupported: {design}")
            local = _asset_dirs(asset_root, page.get("assetDirs", []), "assetDirs")
            selected = tuple(dict.fromkeys(common + local))
            if not selected:
                raise WorkspaceError(f"{project_id}/{page_id} selects no asset directories")
            output = _path(manifest.parent, page.get("output"), "page.output")
            if _within(output, asset_root) or _within(asset_root, output):
                raise WorkspaceError(f"page output overlaps assetRoot: {output}")
            if any(_within(output, old) or _within(old, output) for old in output_paths):
                raise WorkspaceError(f"duplicate or overlapping page output: {output}")
            output_paths.append(output)
            prefab = page.get("prefabPath")
            if (not isinstance(prefab, str) or not prefab.startswith("Assets/")
                    or not prefab.endswith(".prefab") or "\\" in prefab
                    or any(part in (".", "..", "") for part in prefab.split("/"))):
                raise WorkspaceError(f"invalid prefabPath for {project_id}/{page_id}: {prefab!r}")
            target_key = (str(unity_project or project_id), prefab.casefold())
            if target_key in target_paths:
                raise WorkspaceError(f"duplicate prefab path: {prefab}")
            target_paths.add(target_key)
            functional = page.get("functional", {})
            _object(functional, f"{project_id}/{page_id}.functional")
            view = manifest.parent / ".image-to-ui-cache" / project_id / page_id / "assets"
            if _within(view, asset_root):
                raise WorkspaceError(f"generated asset view overlaps assetRoot: {view}")
            if _within(view, output) or _within(output, view):
                raise WorkspaceError(f"page output overlaps generated asset view: {output}")
            pages.append(Page(page_id, project_id, design, asset_root, selected,
                              output, prefab, unity_project, functional, view, known_pages))
        projects.append(Project(project_id, asset_root, unity_project, tuple(pages)))
    for output in output_paths:
        if any(_within(output, root) or _within(root, output) for root in asset_roots):
            raise WorkspaceError(f"page output overlaps an assetRoot: {output}")
    return Workspace(manifest, tuple(projects))


def select_pages(workspace: Workspace, project_id: str | None, page_id: str | None) -> list[Page]:
    projects = [p for p in workspace.projects if project_id is None or p.id == project_id]
    if project_id is not None and not projects:
        raise WorkspaceError(f"unknown project: {project_id}")
    if page_id is not None and project_id is None:
        raise WorkspaceError("--page requires --project")
    pages = [page for project in projects for page in project.pages
             if page_id is None or page.id == page_id]
    if not pages:
        raise WorkspaceError(f"unknown page: {project_id}/{page_id}")
    return pages


def create_overview(workspace: Workspace, pages: list[Page], output: Path) -> dict[str, Any]:
    """Create a contact sheet of source designs for cross-page visual review."""
    from PIL import Image, ImageDraw, ImageOps

    output = output.expanduser().resolve()
    index_path = output.with_suffix(".json")
    for page in pages:
        if output == page.design or index_path == page.design:
            raise WorkspaceError(f"overview output would replace a design image: {page.design}")
    for project in workspace.projects:
        if _within(output, project.asset_root) or _within(index_path, project.asset_root):
            raise WorkspaceError(f"overview output cannot be inside assetRoot: {project.asset_root}")
    columns = min(3, len(pages))
    cell_w, cell_h, padding, label_h = 360, 430, 20, 32
    rows = (len(pages) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w + padding, rows * cell_h + padding), "#25292f")
    draw = ImageDraw.Draw(sheet)
    items: list[dict[str, Any]] = []
    try:
        for i, page in enumerate(pages):
            x = padding + (i % columns) * cell_w
            y = padding + (i // columns) * cell_h
            draw.rounded_rectangle((x, y, x + cell_w - padding, y + cell_h - padding),
                                   radius=8, fill="#353b43")
            draw.text((x + 12, y + 8), f"{page.project_id} / {page.id}", fill="white")
            with Image.open(page.design) as original:
                preview = ImageOps.contain(original.convert("RGB"),
                                           (cell_w - padding - 24, cell_h - padding - label_h - 20))
                width, height = original.size
            px = x + (cell_w - padding - preview.width) // 2
            py = y + label_h + (cell_h - padding - label_h - preview.height) // 2
            sheet.paste(preview, (px, py))
            items.append({"project": page.project_id, "page": page.id,
                          "design": str(page.design), "sourceSize": [width, height],
                          "sheetBounds": [px, py, preview.width, preview.height]})
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"Cannot render workspace overview: {exc}") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    index = {"version": 1, "manifest": str(workspace.manifest),
             "image": str(output), "pages": items}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


_ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".ttf", ".otf", ".ttc", ".meta"}


def sync_asset_view(page: Page) -> Path:
    view = page.view
    marker = view / ".image-to-ui-generated"
    if view.exists() and not marker.is_file() and any(view.iterdir()):
        raise WorkspaceError(f"asset view contains unrecognized files: {view}")
    view.mkdir(parents=True, exist_ok=True)
    marker.write_text("Generated by image-to-ui workspace.py; source files are symlinked.\n", encoding="utf-8")
    wanted: dict[Path, Path] = {}
    for rel_dir in page.selected_dirs:
        source_dir = page.asset_root / rel_dir
        for source in source_dir.rglob("*"):
            if not source.is_file() or source.suffix.lower() not in _ASSET_SUFFIXES:
                continue
            if not _within(source.resolve(), page.asset_root):
                raise WorkspaceError(f"source asset escapes assetRoot: {source}")
            rel = source.relative_to(page.asset_root)
            destination = view / rel
            if destination in wanted and wanted[destination] != source:
                raise WorkspaceError(f"asset view collision: {rel}")
            wanted[destination] = source
    for old in view.rglob("*"):
        if old == marker or old.is_dir():
            continue
        if old not in wanted:
            old.unlink()
    for destination, source in wanted.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink() and destination.resolve() == source.resolve():
            continue
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        try:
            destination.symlink_to(source)
        except OSError as exc:
            raise WorkspaceError(f"Cannot create asset symlink {destination}: {exc}") from exc
    return view


def _structure_nodes(structure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    def visit(node: dict[str, Any], path: str) -> None:
        result[path] = node
        for child in node.get("children") or []:
            if isinstance(child, dict) and isinstance(child.get("name"), str):
                visit(child, path + "/" + child["name"])
    root = structure.get("root")
    if isinstance(root, dict):
        visit(root, "root")
    return result


def validate_functional(page: Page, structure: dict[str, Any]) -> dict[str, Any]:
    """Return the developer handoff and all path/type errors without changing it."""
    nodes = _structure_nodes(structure)
    functional = page.functional
    issues: list[str] = []
    result: dict[str, Any] = {"project": page.project_id, "page": page.id,
                              "actions": [], "navigation": [], "bindings": [], "issues": issues}
    seen_actions: set[str] = set()
    for key in ("actions", "navigation", "bindings"):
        entries = functional.get(key, [])
        if not isinstance(entries, list):
            issues.append(f"functional.{key} must be a list")
            continue
        for index, raw in enumerate(entries):
            if not isinstance(raw, dict):
                issues.append(f"functional.{key}[{index}] must be an object")
                continue
            item = dict(raw)
            path_key = "target" if key == "bindings" else "trigger"
            path = item.get(path_key)
            expected = "text" if key == "bindings" else "button"
            if not isinstance(path, str) or path not in nodes:
                issues.append(f"functional.{key}[{index}] unknown element path: {path!r}")
            elif nodes[path].get("type") != expected:
                issues.append(f"functional.{key}[{index}] needs a {expected} element: {path}")
            if key == "actions":
                action_id = item.get("id")
                if not isinstance(action_id, str) or not action_id.strip():
                    issues.append(f"functional.actions[{index}] needs a nonempty id")
                elif action_id in seen_actions:
                    issues.append(f"duplicate action id: {action_id}")
                else:
                    seen_actions.add(action_id)
            elif key == "navigation":
                if item.get("to") not in page.known_pages:
                    issues.append(f"functional.navigation[{index}] unknown page: {item.get('to')!r}")
            elif not isinstance(item.get("source"), str) or not item["source"].strip():
                issues.append(f"functional.bindings[{index}] needs a nonempty source")
            result[key].append(item)
    return result


def _asset_references(structure: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for node in _structure_nodes(structure).values():
        asset = node.get("asset")
        if isinstance(asset, str) and asset:
            refs.add(asset)
        variants = (node.get("state") or {}).get("variants", {})
        if isinstance(variants, dict):
            for changes in variants.values():
                if isinstance(changes, dict):
                    for patch in changes.values():
                        if isinstance(patch, dict) and isinstance(patch.get("asset"), str):
                            refs.add(patch["asset"])
    return refs


def _selected_asset_files(page: Page) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for rel_dir in page.selected_dirs:
        for path in (page.asset_root / rel_dir).rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                if not _within(path.resolve(), page.asset_root):
                    raise WorkspaceError(f"source asset escapes assetRoot: {path}")
                files[path.relative_to(page.asset_root).as_posix()] = path
    return files


def build_workspace_report(workspace: Workspace, pages: list[Page]) -> dict[str, Any]:
    """Inspect page structures and report exact-byte shared art candidates."""
    page_reports: list[dict[str, Any]] = []
    by_hash: dict[tuple[str, str], dict[str, set[str]]] = {}
    for page in pages:
        state_path = page.output / "workflow_state.json"
        status = "unprepared"
        if state_path.is_file():
            try:
                status = json.loads(state_path.read_text(encoding="utf-8")).get("status", "unknown")
            except (OSError, json.JSONDecodeError):
                status = "invalid_state"
        issues: list[str] = []
        used: list[str] = []
        structure_path = page.output / "ui_structure.json"
        if structure_path.is_file():
            try:
                structure = _object(json.loads(structure_path.read_text(encoding="utf-8")), "ui_structure")
                contract = validate_functional(page, structure)
                issues.extend(contract["issues"])
                if page.functional:
                    page.output.mkdir(parents=True, exist_ok=True)
                    (page.output / "integration_contract.json").write_text(
                        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                available = _selected_asset_files(page)
                for ref in sorted(_asset_references(structure)):
                    normalized = ref.replace("\\", "/")
                    if normalized in available:
                        matches = [(normalized, available[normalized])]
                    elif "/" not in normalized:
                        matches = [(rel, path) for rel, path in available.items()
                                   if Path(rel).name.casefold() == normalized.casefold()]
                    else:
                        matches = []
                    if len(matches) != 1:
                        issues.append(f"asset {ref!r} has {len(matches)} matches in selected directories")
                        continue
                    rel, asset_path = matches[0]
                    used.append(rel)
                    digest = hashlib.sha256(asset_path.read_bytes()).hexdigest()
                    group = by_hash.setdefault((page.project_id, digest), {"pages": set(), "paths": set()})
                    group["pages"].add(f"{page.project_id}/{page.id}")
                    group["paths"].add(rel)
            except (OSError, json.JSONDecodeError, WorkspaceError) as exc:
                issues.append(f"cannot read structure: {exc}")
        elif page.functional:
            issues.append("functional contract cannot be checked until ui_structure.json exists")
        page_reports.append({"project": page.project_id, "page": page.id,
                             "status": status, "output": str(page.output),
                             "usedAssets": used, "issues": issues})
    candidates = [
        {"project": project, "sha256": digest,
         "pages": sorted(group["pages"]), "paths": sorted(group["paths"])}
        for (project, digest), group in by_hash.items() if len(group["pages"]) >= 2
    ]
    candidates.sort(key=lambda item: (item["project"], item["sha256"]))
    return {"version": 1, "manifest": str(workspace.manifest),
            "pages": page_reports, "sharedCandidates": candidates}


def run_workflow_pages(pages: list[Page], command: str, runner=None) -> list[dict[str, Any]]:
    """Run the existing single-page workflow independently for each page."""
    if command not in {"prepare", "check", "finalize"}:
        raise WorkspaceError(f"unsupported page workflow command: {command}")
    script = Path(__file__).with_name("workflow.py")
    results: list[dict[str, Any]] = []
    for page in pages:
        try:
            view = sync_asset_view(page)
            args = [sys.executable, "-B", str(script), command]
            if command == "prepare":
                args += ["--design", str(page.design), "--assets", str(view)]
            args += ["--output", str(page.output)]
            if runner is None:
                process = subprocess.run(args, text=True, capture_output=True, check=False)
                code, detail = process.returncode, (process.stdout + process.stderr).strip()
            else:
                code, detail = runner(args), ""
            results.append({"project": page.project_id, "page": page.id,
                            "status": "ok" if code == 0 else "failed",
                            "exitCode": code, "detail": detail})
        except (OSError, WorkspaceError) as exc:
            results.append({"project": page.project_id, "page": page.id,
                            "status": "failed", "exitCode": 1, "detail": str(exc)})
    return results


def build_requests(pages: list[Page]) -> tuple[list[dict[str, Any]], list[str]]:
    """Emit only fresh, complete, non-overwriting single-flight Bridge requests."""
    requests: list[dict[str, Any]] = []
    issues: list[str] = []
    multi_project = len({page.project_id for page in pages}) > 1
    for page in pages:
        label = f"{page.project_id}/{page.id}"
        if multi_project and page.unity_project is None:
            issues.append(f"{label}: unityProject is required for cross-project build requests")
            continue
        structure_path = page.output / "ui_structure.json"
        report_path = page.output / "completion_report.json"
        state_path = page.output / "workflow_state.json"
        if not structure_path.is_file() or not report_path.is_file() or not state_path.is_file():
            issues.append(f"{label}: incomplete page; structure, workflow state, or completion report missing")
            continue
        try:
            completion = _object(json.loads(report_path.read_text(encoding="utf-8")), "completion report")
            state = _object(json.loads(state_path.read_text(encoding="utf-8")), "workflow state")
            digest = hashlib.sha256(structure_path.read_bytes()).hexdigest()
            if (completion.get("complete") is not True or state.get("status") != "completed"
                    or (completion.get("structure") or {}).get("sha256") != digest):
                issues.append(f"{label}: incomplete or stale page; rerun check and finalize")
                continue
            if page.functional:
                contract = validate_functional(page, _object(json.loads(structure_path.read_text(encoding="utf-8")), "ui_structure"))
                if contract["issues"]:
                    issues.extend(f"{label}: {item}" for item in contract["issues"])
                    continue
            if page.unity_project is not None and (page.unity_project / page.prefab_path).exists():
                issues.append(f"{label}: Prefab already exists: {page.unity_project / page.prefab_path}")
                continue
            requests.append({"project": page.project_id, "page": page.id,
                             "unityProject": str(page.unity_project) if page.unity_project else None,
                             "command": "build_ui_prefab", "params": {
                                 "structurePath": str(structure_path),
                                 "assetsPath": str(page.asset_root),
                                 "prefabPath": page.prefab_path,
                                 "overwrite": False}})
        except (OSError, json.JSONDecodeError, WorkspaceError) as exc:
            issues.append(f"{label}: cannot prepare build request: {exc}")
    return requests, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "overview", "prepare", "check", "finalize", "report", "build-requests"))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--project")
    parser.add_argument("--page")
    parser.add_argument("--output", type=Path, help="Overview, report, or request file; defaults beside manifest")
    args = parser.parse_args(argv)
    try:
        workspace = load_workspace(args.manifest)
        pages = select_pages(workspace, args.project, args.page)
        if args.command == "validate":
            result: dict[str, Any] = {"valid": True, "projects": len(workspace.projects), "selectedPages": len(pages)}
        elif args.command == "overview":
            result = create_overview(workspace, pages,
                                     args.output or workspace.manifest.parent / "workspace_overview.png")
        elif args.command in ("prepare", "check", "finalize"):
            result = {"results": run_workflow_pages(pages, args.command)}
        elif args.command == "report":
            result = build_workspace_report(workspace, pages)
            output = (args.output or workspace.manifest.parent / "workspace_report.json").resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result["reportPath"] = str(output)
        else:
            requests, issues = build_requests(pages)
            result = {"requests": requests, "issues": issues}
            output = (args.output or workspace.manifest.parent / "workspace_build_requests.json").resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result["requestPath"] = str(output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command in ("prepare", "check", "finalize"):
            return 1 if any(item["status"] != "ok" for item in result["results"]) else 0
        return 1 if result.get("issues") else 0
    except WorkspaceError as exc:
        print(f"Workspace error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

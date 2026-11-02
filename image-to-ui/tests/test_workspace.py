from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from workspace import (  # noqa: E402
    WorkspaceError, build_requests, build_workspace_report, create_overview, load_workspace,
    run_workflow_pages, select_pages, sync_asset_view, validate_functional,
)


class WorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = self.root / "ui_workspace.json"
        self.data = {
            "version": 1,
            "projects": [
                {"id": "emberfall", "assetRoot": "emberfall-assets",
                 "commonAssetDirs": ["Common"],
                 "pages": [
                     {"id": "market", "design": "design/market.png",
                      "assetDirs": ["Pages/market"], "output": "out/market",
                      "prefabPath": "Assets/UI/Market.prefab"},
                     {"id": "inventory", "design": "design/inventory.png",
                      "assetDirs": ["Pages/inventory"], "output": "out/inventory",
                      "prefabPath": "Assets/UI/Inventory.prefab"},
                 ]},
                {"id": "othergame", "assetRoot": "othergame-assets",
                 "commonAssetDirs": ["Common"],
                 "pages": [{"id": "market", "design": "design/other.png",
                            "assetDirs": ["Pages/market"], "output": "out/other-market",
                            "prefabPath": "Assets/UI/OtherMarket.prefab"}]},
            ],
        }
        for name in ["emberfall-assets/Common", "emberfall-assets/Pages/market",
                     "emberfall-assets/Pages/inventory", "othergame-assets/Common",
                     "othergame-assets/Pages/market", "design"]:
            (self.root / name).mkdir(parents=True)
        for name in ["design/market.png", "design/inventory.png", "design/other.png"]:
            (self.root / name).write_bytes(b"design")
        (self.root / "emberfall-assets/Common/frame.png").write_bytes(b"shared")
        (self.root / "emberfall-assets/Pages/market/coin.png").write_bytes(b"market")
        (self.root / "emberfall-assets/Pages/inventory/bag.png").write_bytes(b"inventory")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_manifest(self) -> None:
        self.manifest.write_text(json.dumps(self.data), encoding="utf-8")

    def test_two_projects_and_page_asset_view_are_isolated(self) -> None:
        self.write_manifest()
        workspace = load_workspace(self.manifest)
        self.assertEqual(len(select_pages(workspace, None, None)), 3)
        page = select_pages(workspace, "emberfall", "market")[0]
        view = sync_asset_view(page)
        self.assertTrue((view / "Common/frame.png").is_symlink())
        self.assertEqual((view / "Pages/market/coin.png").read_bytes(), b"market")
        self.assertFalse((view / "Pages/inventory/bag.png").exists())
        self.assertEqual([p.id for p in select_pages(workspace, "othergame", None)], ["market"])

    def test_duplicate_output_and_prefab_are_rejected(self) -> None:
        self.data["projects"][0]["pages"][1]["output"] = "out/market"
        self.write_manifest()
        with self.assertRaisesRegex(WorkspaceError, "output"):
            load_workspace(self.manifest)
        self.data["projects"][0]["pages"][1]["output"] = "out/inventory"
        self.data["projects"][0]["pages"][1]["prefabPath"] = "Assets/UI/Market.prefab"
        self.write_manifest()
        with self.assertRaisesRegex(WorkspaceError, "prefab"):
            load_workspace(self.manifest)

    def test_escape_and_duplicate_ids_are_rejected(self) -> None:
        self.data["projects"][0]["pages"][0]["assetDirs"] = ["../outside"]
        self.write_manifest()
        with self.assertRaisesRegex(WorkspaceError, "assetDirs"):
            load_workspace(self.manifest)
        self.data["projects"][0]["pages"][0]["assetDirs"] = ["Pages/market"]
        self.data["projects"][0]["pages"][1]["id"] = "market"
        self.write_manifest()
        with self.assertRaisesRegex(WorkspaceError, "duplicate page"):
            load_workspace(self.manifest)

    def test_output_cannot_contain_generated_asset_view(self) -> None:
        self.data["projects"][0]["pages"][0]["output"] = ".image-to-ui-cache/emberfall"
        self.write_manifest()
        with self.assertRaisesRegex(WorkspaceError, "asset view"):
            load_workspace(self.manifest)

    def test_symlinked_source_cannot_escape_asset_root(self) -> None:
        outside = self.root / "outside.png"
        outside.write_bytes(b"private")
        (self.root / "emberfall-assets/Pages/market/leak.png").symlink_to(outside)
        self.write_manifest()
        page = select_pages(load_workspace(self.manifest), "emberfall", "market")[0]
        with self.assertRaisesRegex(WorkspaceError, "escapes assetRoot"):
            sync_asset_view(page)

    def test_functional_contract_checks_paths_types_and_navigation(self) -> None:
        self.data["projects"][0]["pages"][0]["functional"] = {
            "actions": [{"id": "buy", "trigger": "root/buy"}],
            "bindings": [{"target": "root/price", "source": "market.price"}],
            "navigation": [{"trigger": "root/buy", "to": "inventory"}],
        }
        self.write_manifest()
        page = select_pages(load_workspace(self.manifest), "emberfall", "market")[0]
        structure = {"root": {"type": "container", "name": "root", "children": [
            {"type": "button", "name": "buy", "children": []},
            {"type": "text", "name": "price", "text": "100"},
        ]}}
        contract = validate_functional(page, structure)
        self.assertEqual(contract["issues"], [])
        self.assertEqual(contract["actions"][0]["id"], "buy")
        self.data["projects"][0]["pages"][0]["functional"]["actions"][0]["trigger"] = "root/price"
        self.data["projects"][0]["pages"][0]["functional"]["navigation"][0]["to"] = "missing"
        self.write_manifest()
        bad_page = select_pages(load_workspace(self.manifest), "emberfall", "market")[0]
        bad = validate_functional(bad_page, structure)
        self.assertTrue(any("button" in issue for issue in bad["issues"]))
        self.assertTrue(any("unknown page" in issue for issue in bad["issues"]))

    def test_report_finds_identical_assets_across_pages(self) -> None:
        (self.root / "emberfall-assets/Pages/inventory/coin_clone.png").write_bytes(b"market")
        self.write_manifest()
        workspace = load_workspace(self.manifest)
        for page in select_pages(workspace, "emberfall", None):
            page.output.mkdir(parents=True)
            asset = ("Pages/market/coin.png" if page.id == "market"
                     else "Pages/inventory/coin_clone.png")
            (page.output / "ui_structure.json").write_text(json.dumps({
                "root": {"type": "container", "name": "root", "children": [
                    {"type": "image", "name": "icon", "asset": asset}]}}))
        report = build_workspace_report(workspace, select_pages(workspace, "emberfall", None))
        candidates = report["sharedCandidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(set(candidates[0]["pages"]), {"emberfall/market", "emberfall/inventory"})
        self.assertEqual(len(candidates[0]["paths"]), 2)

    def test_overview_shows_all_selected_pages_and_writes_index(self) -> None:
        from PIL import Image
        for name, size in [("market.png", (200, 100)), ("inventory.png", (100, 200)),
                           ("other.png", (120, 120))]:
            Image.new("RGB", size, "navy").save(self.root / "design" / name)
        self.write_manifest()
        workspace = load_workspace(self.manifest)
        output = self.root / "overview.png"
        index = create_overview(workspace, select_pages(workspace, None, None), output)
        self.assertTrue(output.is_file())
        with Image.open(output) as sheet:
            self.assertGreater(sheet.width, 300)
            self.assertGreater(sheet.height, 100)
        self.assertEqual(len(index["pages"]), 3)
        self.assertEqual(index["pages"][0]["project"], "emberfall")
        self.assertEqual(index["pages"][2]["page"], "market")
        self.assertTrue(output.with_suffix(".json").is_file())

    def test_batch_prepare_keeps_page_outputs_separate(self) -> None:
        self.write_manifest()
        workspace = load_workspace(self.manifest)
        calls = []
        def fake_runner(command):
            calls.append(command)
            return 0
        results = run_workflow_pages(select_pages(workspace, "emberfall", None),
                                     "prepare", runner=fake_runner)
        self.assertEqual([r["status"] for r in results], ["ok", "ok"])
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0][-1], calls[1][-1])
        self.assertIn("--design", calls[0])
        self.assertTrue((self.root / ".image-to-ui-cache/emberfall/market/assets/Common/frame.png").is_file())

    def test_real_prepare_runs_three_isolated_pages(self) -> None:
        from PIL import Image
        for name in ["design/market.png", "design/inventory.png", "design/other.png"]:
            Image.new("RGB", (32, 32), "navy").save(self.root / name)
        for name in ["emberfall-assets/Common/frame.png", "emberfall-assets/Pages/market/coin.png",
                     "emberfall-assets/Pages/inventory/bag.png", "othergame-assets/Common/frame.png"]:
            Image.new("RGBA", (8, 8), "white").save(self.root / name)
        (self.root / "othergame-assets/Pages/market/item.png").write_bytes(b"")
        Image.new("RGBA", (8, 8), "red").save(self.root / "othergame-assets/Pages/market/item.png")
        self.write_manifest()
        workspace = load_workspace(self.manifest)
        pages = select_pages(workspace, None, None)
        results = run_workflow_pages(pages, "prepare")
        self.assertEqual([r["status"] for r in results], ["ok", "ok", "ok"], results)
        for page in pages:
            state = json.loads((page.output / "workflow_state.json").read_text())
            self.assertEqual(state["status"], "prepared")
        market_inventory = json.loads((pages[0].output / "assets/assets_inventory.json").read_text())
        paths = {a["path"] for a in market_inventory["assets"]}
        self.assertIn("Pages/market/coin.png", paths)
        self.assertNotIn("Pages/inventory/bag.png", paths)

    def test_build_requests_refuse_incomplete_or_existing_prefab(self) -> None:
        unity = self.root / "unity"
        (unity / "Assets/UI").mkdir(parents=True)
        self.data["projects"][0]["unityProject"] = "unity"
        self.write_manifest()
        workspace = load_workspace(self.manifest)
        pages = select_pages(workspace, "emberfall", None)
        market, inventory = pages
        for page in pages:
            page.output.mkdir(parents=True)
            (page.output / "ui_structure.json").write_text(json.dumps({"root": {
                "type": "container", "name": "root", "children": []}}))
        digest = hashlib.sha256((market.output / "ui_structure.json").read_bytes()).hexdigest()
        (market.output / "completion_report.json").write_text(json.dumps({
            "complete": True, "structure": {"sha256": digest}}))
        (market.output / "workflow_state.json").write_text('{"status":"completed"}')
        requests, issues = build_requests(pages)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["params"]["overwrite"], False)
        mcp_requests, mcp_issues = build_requests(pages, backend="mcp")
        self.assertEqual(len(mcp_requests), 1)
        self.assertEqual(mcp_issues, issues)
        self.assertEqual(mcp_requests[0]["tool"], "image_to_ui_build_prefab")
        self.assertNotIn("command", mcp_requests[0])
        self.assertEqual(mcp_requests[0]["params"]["overwrite"], False)
        self.assertTrue(any("incomplete" in issue for issue in issues))
        (unity / "Assets/UI/Market.prefab").write_text("existing")
        requests, issues = build_requests(pages)
        self.assertEqual(requests, [])
        self.assertTrue(any("already exists" in issue for issue in issues))

    def test_multi_project_build_requests_need_project_identity(self) -> None:
        self.write_manifest()
        workspace = load_workspace(self.manifest)
        pages = select_pages(workspace, None, None)
        for page in pages:
            page.output.mkdir(parents=True)
            structure = page.output / "ui_structure.json"
            structure.write_text('{"root":{"type":"container","name":"root","children":[]}}')
            digest = hashlib.sha256(structure.read_bytes()).hexdigest()
            (page.output / "completion_report.json").write_text(json.dumps({
                "complete": True, "structure": {"sha256": digest}}))
            (page.output / "workflow_state.json").write_text('{"status":"completed"}')
        requests, issues = build_requests(pages)
        self.assertEqual(requests, [])
        self.assertTrue(any("unityProject" in issue for issue in issues))
        for project in self.data["projects"]:
            unity = self.root / (project["id"] + "-unity")
            (unity / "Assets").mkdir(parents=True)
            project["unityProject"] = unity.name
        self.write_manifest()
        requests, issues = build_requests(select_pages(load_workspace(self.manifest), None, None))
        self.assertEqual(issues, [])
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[0]["unityProject"], str((self.root / "emberfall-unity").resolve()))
        self.assertEqual(requests[2]["unityProject"], str((self.root / "othergame-unity").resolve()))


if __name__ == "__main__":
    unittest.main()

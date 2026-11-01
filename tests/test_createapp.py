import base64
import copy
import hashlib
from http.client import IncompleteRead
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import DEFAULTS, roles_for
from createapp import AppServer, main
from engine import ConfigError, blob_hash, fetch_blob, initialize, preview, validate
from policy import policy, wrapper
from updates import MAX_RELEASE_BYTES, check_for_updates, install_update, internet_available, offer_update, update_message

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = copy.deepcopy(DEFAULTS)
        self.config.update(directory="mi-app", stack="react-vite")
        (self.root / "mi-app").mkdir()

    def fake(self, repo, source, entry, cache):
        return ("fixture: " + repo + "/" + entry["path"]).encode()

    def test_defaults_optional_and_single_coordinator(self):
        p = preview(self.config, self.root)
        self.assertNotIn("matt", p["config"]["packs"])
        self.assertNotIn("graphify", p["config"]["packs"])
        self.assertIn("workflow", p["roles"])
        self.assertNotIn("matt-workflow", p["roles"])
        self.assertNotIn("composition", p["roles"])

    def test_impeccable_is_optional_and_selected_explicitly(self):
        default = preview(self.config, self.root)
        self.assertNotIn("impeccable", default["config"]["packs"])
        self.assertNotIn("impeccable", default["roles"])
        self.assertNotIn("pbakaus/impeccable", {source["repo"] for source in default["sources"]})
        self.config["packs"].append("impeccable")
        selected = preview(self.config, self.root)
        self.assertIn("impeccable", selected["roles"])
        self.assertIn(".agents/skills/ca-impeccable/SKILL.md", selected["files"])
        self.assertIn("pbakaus/impeccable", {source["repo"] for source in selected["sources"]})
        self.assertTrue(any("Impeccable" in warning for warning in selected["warnings"]))
        self.config["skills"] = ["workflow"]
        excluded = preview(self.config, self.root)
        self.assertNotIn("impeccable", excluded["roles"])
        self.assertNotIn("pbakaus/impeccable", {source["repo"] for source in excluded["sources"]})
        self.assertFalse(any("Impeccable" in warning for warning in excluded["warnings"]))

    def test_impeccable_offline_install_is_manual_and_reference_only(self):
        self.config.update(packs=["impeccable"], coordinator="simple", agents=["copilot", "claude"], vercel_react=False, vercel_web=False)
        with patch("urllib.request.urlopen", side_effect=AssertionError("network should not be used")):
            initialize(self.config, self.root, cache=self.root / "empty-cache")
        target = self.root / "mi-app"
        for skill_root in (".agents/skills", ".claude/skills"):
            rendered = (target / skill_root / "ca-impeccable/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("disable-model-invocation: true", rendered)
            self.assertIn("sin motor ni launcher", rendered)
            self.assertIn("No ejecutar `impeccable context`", rendered)
            self.assertIn("reference/craft-floor.md", rendered)
            self.assertIn("no están incluidos en este perfil", rendered)
        lock = json.loads((target / ".createapp/sources.lock.json").read_text(encoding="utf-8"))
        source = lock["sources"]["pbakaus/impeccable"]
        vendor = target / ".createapp/vendor/pbakaus/impeccable"
        for entry in source["files"]:
            data = (vendor / entry["path"]).read_bytes()
            self.assertEqual(blob_hash(data), entry["sha"])
            self.assertEqual(len(data), entry["size"])
            self.assertTrue(entry["path"].endswith(".md") or entry["path"] == "LICENSE")
        self.assertTrue((vendor / "LICENSE").is_file())
        self.assertTrue((vendor / "NOTICE.md").is_file())
        self.assertFalse((vendor / ".agents/skills/impeccable/scripts").exists())
        self.assertFalse((target / ".github/hooks").exists())
        self.assertFalse((target / ".claude/settings.json").exists())
        self.assertFalse((target / ".createapp/tools").exists())

    def test_find_skills_is_optional_and_selected_explicitly(self):
        default = preview(self.config, self.root)
        self.assertNotIn("find-skills", default["config"]["packs"])
        self.assertNotIn("find-skills", default["roles"])
        self.assertNotIn("vercel-labs/skills", {source["repo"] for source in default["sources"]})
        self.config["packs"].append("find-skills")
        selected = preview(self.config, self.root)
        self.assertIn("find-skills", selected["roles"])
        self.assertIn(".agents/skills/ca-find-skills/SKILL.md", selected["files"])
        self.assertIn("vercel-labs/skills", {source["repo"] for source in selected["sources"]})
        self.assertTrue(any("Find Skills" in warning for warning in selected["warnings"]))
        self.config["skills"] = ["workflow"]
        excluded = preview(self.config, self.root)
        self.assertNotIn("find-skills", excluded["roles"])
        self.assertNotIn("vercel-labs/skills", {source["repo"] for source in excluded["sources"]})
        self.assertFalse(any("Find Skills" in warning for warning in excluded["warnings"]))

    def test_find_skills_offline_install_does_not_install_cli_or_other_skills(self):
        self.config.update(packs=["find-skills"], coordinator="simple", agents=["copilot", "claude"], vercel_react=False, vercel_web=False)
        with patch("urllib.request.urlopen", side_effect=AssertionError("network should not be used")):
            initialize(self.config, self.root, cache=self.root / "empty-cache")
        target = self.root / "mi-app"
        for skill_root in (".agents/skills", ".claude/skills"):
            rendered = (target / skill_root / "ca-find-skills/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("disable-model-invocation: true", rendered)
            self.assertIn("`npx skills find` requiere Node.js/npm", rendered)
            self.assertIn("sin autorización explícita", rendered)
            self.assertIn("No usar `-g -y` por defecto", rendered)
            self.assertFalse((target / skill_root / "find-skills").exists())
        lock = json.loads((target / ".createapp/sources.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(set(lock["sources"]), {"vercel-labs/skills"})
        source = lock["sources"]["vercel-labs/skills"]
        self.assertEqual({entry["path"] for entry in source["files"]}, {"LICENSE", "skills/find-skills/SKILL.md"})
        for entry in source["files"]:
            data = (target / ".createapp/vendor/vercel-labs/skills" / entry["path"]).read_bytes()
            self.assertEqual(blob_hash(data), entry["sha"])
            self.assertEqual(len(data), entry["size"])
        self.assertFalse((target / "node_modules").exists())
        self.assertFalse((target / "package.json").exists())
        self.assertFalse((target / ".createapp/tools").exists())

    def test_matt_replaces_coordinator(self):
        self.config["packs"].append("matt")
        self.config["coordinator"] = "matt"
        roles = roles_for(self.config)
        self.assertIn("matt-workflow", roles)
        self.assertNotIn("workflow", roles)
        self.assertNotIn("debug", roles)

    def test_frontmatter_quotes_descriptions_with_colons(self):
        from catalog import ROLES
        for name, data in ROLES.items():
            rendered = wrapper(name, data, self.config)
            description_line = next(x for x in rendered.splitlines() if x.startswith('description: '))
            self.assertEqual(json.loads(description_line[len('description: '):]), data[3])

    def test_stack_scoping(self):
        self.config.update(stack="python", template="config-only", database="postgres")
        roles = preview(self.config, self.root)["roles"]
        self.assertNotIn("react", roles)
        self.assertNotIn("web-review", roles)
        self.assertIn("postgres", roles)
        self.config["stack"] = "nextjs"
        self.assertIn("next", preview(self.config, self.root)["roles"])

    def test_traversal_absolute_and_wrong_types(self):
        for directory in ("../outside", "/tmp/outside", "C:\\elsewhere", "x/../../outside"):
            with self.subTest(directory=directory), self.assertRaises(ConfigError): validate({"directory": directory}, self.root)
        for raw in ({"parallel": "yes"}, {"packs": "matt"}, {"packs": ["unknown"]}, {"agent":"unknown"}, {"unexpected":True}):
            with self.subTest(raw=raw), self.assertRaises(ConfigError): validate(raw, self.root)

    def test_symlink_refused(self):
        outside = self.root / "outside"
        outside.mkdir()
        try: (self.root / "linked").symlink_to(outside, target_is_directory=True)
        except OSError: self.skipTest("Symlinks unavailable")
        with self.assertRaises(ConfigError): validate({"directory":"linked/app"}, self.root)

    def test_skill_conflict_preserves_existing(self):
        target = self.root / "mi-app"
        (target / "package.json").write_text('{"original":true}')
        path = target / ".agents/skills/ca-workflow/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("user-owned skill")
        self.assertIn(".agents/skills/ca-workflow/SKILL.md", preview(self.config, self.root)["conflicts"])
        with self.assertRaises(ConfigError): initialize(self.config, self.root, fetcher=self.fake)
        self.assertEqual(path.read_text(), "user-owned skill")
        self.assertEqual((target / "package.json").read_text(), '{"original":true}')

    def test_config_only_appends_instructions_and_keeps_app(self):
        target = self.root / "mi-app"
        target.mkdir(exist_ok=True)
        (target / "AGENTS.md").write_text("Existing rules\n")
        (target / ".gitignore").write_text("custom-ignore\n")
        (target / "app.py").write_text("print('existing')\n")
        self.config.update(template="config-only", stack="auto")
        initialize(self.config, self.root, fetcher=self.fake)
        self.assertTrue((target / "AGENTS.md").read_text().startswith("Existing rules\n"))
        self.assertTrue((target / ".gitignore").read_text().startswith("custom-ignore\n"))
        self.assertEqual((target / "app.py").read_text(), "print('existing')\n")
        self.assertFalse((target / "package.json").exists())

    def test_failed_download_leaves_no_project(self):
        def fail(*args): raise OSError("network failure")
        with self.assertRaises(OSError): initialize(self.config, self.root, fetcher=fail)
        self.assertFalse((self.root / "mi-app/.createapp").exists())

    def test_source_hash_verification_rejects_tampering(self):
        expected = b"expected content"
        entry = {"path":"SKILL.md", "sha":blob_hash(expected), "size":len(expected)}
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): return b"tampered content"
        with patch("urllib.request.urlopen", return_value=Response()), self.assertRaises(ConfigError):
            fetch_blob("owner/repo", {"commit":"a"*40}, entry, self.root / "cache")

    def test_incremental_skills_preserve_existing_installation(self):
        from engine import installation, preview_additions, install_additions
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        original_rules = (target / "AGENTS.md").read_bytes()
        original_policy = (target / ".createapp/POLICY.md").read_bytes()
        original_skill = (target / ".agents/skills/ca-workflow/SKILL.md").read_bytes()
        state = installation(target)
        self.assertIn("workflow", state["installed"])
        self.assertIn("find-skills", state["available"])
        planned = preview_additions(["find-skills"], target)
        self.assertEqual(planned["roles"], ["find-skills"])
        install_additions(["find-skills"], target, fetcher=self.fake)
        self.assertEqual((target / "AGENTS.md").read_bytes(), original_rules)
        self.assertTrue((target / ".createapp/POLICY.md").read_bytes().startswith(original_policy))
        self.assertEqual((target / ".agents/skills/ca-workflow/SKILL.md").read_bytes(), original_skill)
        self.assertTrue((target / ".agents/skills/ca-find-skills/SKILL.md").is_file())
        self.assertNotIn("find-skills", installation(target)["available"])
        self.assertEqual(preview_additions(["find-skills"], target)["roles"], [])

    def test_complete_project_and_no_reinstall(self):
        result = initialize(self.config, self.root, fetcher=self.fake)
        target = Path(result["target"])
        self.assertFalse((target / "src").exists())
        self.assertFalse((target / "package.json").exists())
        self.assertTrue((target / ".createapp/START_HERE.md").is_file())
        self.assertIn(".createapp/POLICY.md", (target / ".github/copilot-instructions.md").read_text())
        self.assertTrue((target / ".agents/skills/ca-workflow/SKILL.md").is_file())
        self.assertFalse((target / ".agents/skills/using-superpowers").exists())
        self.assertFalse((target / ".createapp/setup_graphify.py").exists())
        self.assertFalse((target / "node_modules").exists())
        self.assertFalse((target / ".git").exists())
        with self.assertRaises(ConfigError): initialize(self.config, self.root, fetcher=self.fake)

    def test_incremental_download_failure_changes_nothing(self):
        from engine import install_additions
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        before = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        with self.assertRaises(OSError):
            install_additions(["impeccable"], target, fetcher=lambda *args: (_ for _ in ()).throw(OSError("offline")))
        after = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_incremental_detects_policy_changes_during_preparation(self):
        from engine import install_additions
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        policy_path = target / ".createapp/POLICY.md"
        def edited(repo, source, entry, cache):
            policy_path.write_text("user changed policy", encoding="utf-8")
            return self.fake(repo, source, entry, cache)
        with self.assertRaises(ConfigError): install_additions(["find-skills"], target, fetcher=edited)
        self.assertEqual(policy_path.read_text(), "user changed policy")
        self.assertFalse((target / ".agents/skills/ca-find-skills").exists())

    def test_incremental_preserves_old_sources_when_provider_commit_changes(self):
        from engine import LOCK, install_additions, installation
        self.config["skills"] = ["workflow", "visual"]
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        repo = "anthropics/skills"
        previous = json.loads((target / ".createapp/sources.lock.json").read_text(encoding="utf-8"))["sources"][repo]
        vendor = target / ".createapp/vendor" / repo
        original_files = {path.relative_to(vendor): path.read_bytes() for path in vendor.rglob("*") if path.is_file()}
        newer = copy.deepcopy(LOCK)
        newer["sources"][repo]["commit"] = "a" * 40
        with patch("engine.LOCK", newer):
            install_additions(["browser-test"], target, fetcher=self.fake)
        lock = json.loads((target / ".createapp/sources.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["sources"][repo], previous)
        for path, data in original_files.items(): self.assertEqual((vendor / path).read_bytes(), data)
        snapshot = lock["additions"][0]["sources_lock"]
        self.assertEqual(json.loads((target / snapshot).read_text(encoding="utf-8"))["sources"][repo]["commit"], "a" * 40)
        wrapper_text = (target / ".agents/skills/ca-browser-test/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(".createapp/additions/", wrapper_text)
        self.assertNotIn("browser-test", installation(target)["available"])

    def test_incremental_preserves_agents_and_never_switches_coordinator(self):
        from engine import installation, install_additions, preview_additions
        self.config["agents"] = ["copilot", "claude"]
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        state = installation(target)
        self.assertNotIn("matt-workflow", state["available"])
        with self.assertRaises(ConfigError): preview_additions(["matt-workflow"], target)
        with self.assertRaises(ConfigError): preview_additions(["missing-skill"], target)
        install_additions(["impeccable"], target, fetcher=self.fake)
        for root in (".agents/skills", ".claude/skills"):
            self.assertTrue((target / root / "ca-impeccable/SKILL.md").is_file())
        self.assertEqual(installation(target)["config"]["coordinator"], "superpowers")

    def test_incremental_no_selection_is_a_noop(self):
        from engine import install_additions
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        before = (target / ".createapp/config.json").read_bytes()
        result = install_additions([], target, fetcher=lambda *args: self.fail("No downloads expected"))
        self.assertEqual(result["roles"], 0)
        self.assertEqual((target / ".createapp/config.json").read_bytes(), before)
        self.assertFalse((target / ".createapp/additions").exists())

    def test_incremental_rejects_changes_after_confirmation(self):
        from engine import install_additions, preview_additions
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        planned = preview_additions(["find-skills"], target)
        policy_path = target / ".createapp/POLICY.md"
        policy_path.write_bytes(policy_path.read_bytes() + b"\nUser decision\n")
        with self.assertRaises(ConfigError):
            install_additions(["find-skills"], target, fetcher=self.fake, expected_hash=planned["config_hash"])
        self.assertFalse((target / ".agents/skills/ca-find-skills").exists())

    def test_incremental_rolls_back_write_failure(self):
        from engine import install_additions
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        before = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        import os
        replace = os.replace
        def fail_on_config(source, destination):
            if Path(destination) == target / ".createapp/config.json": raise OSError("write failed")
            return replace(source, destination)
        with patch("engine.os.replace", side_effect=fail_on_config), self.assertRaises(OSError):
            install_additions(["find-skills"], target, fetcher=self.fake)
        after = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_incremental_terminal_offers_only_missing_skills_and_can_cancel(self):
        from terminal import run
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        before = (target / ".createapp/config.json").read_bytes()
        class Prompts:
            def ask(inner, kind, message, choices=None, default=None):
                if kind == "multi":
                    available = {name for name, label in choices}
                    self.assertNotIn("workflow", available)
                    self.assertIn("find-skills", available)
                    self.assertEqual(default, [])
                    return ["find-skills"]
                self.assertEqual(kind, "confirm")
                return False
        with patch("sys.stdout", new_callable=StringIO): self.assertIsNone(run(target, prompts=Prompts()))
        self.assertEqual((target / ".createapp/config.json").read_bytes(), before)

    def test_incremental_ux_search_finds_added_sources_offline(self):
        from engine import install_additions
        from tooling import ux_search
        self.config.update(packs=[], coordinator="simple", vercel_react=False, vercel_web=False)
        target = self.root / "mi-app"
        with patch("urllib.request.urlopen", side_effect=AssertionError("offline")), patch("sys.stdout", new_callable=StringIO) as stdout:
            initialize(self.config, self.root)
            install_additions(["ux"], target)
            ux_search(target, ["minimal productivity", "--design-system", "-f", "markdown"])
        self.assertTrue(stdout.getvalue())

    def test_policy_changes_with_choices(self):
        self.config.update(autonomy="autonomous",testing="strict",parallel=True,design="existing")
        text = policy(self.config)
        self.assertIn("observar una prueba fallar", text)
        self.assertIn("Se permite delegar", text)
        self.assertIn("Conservar la identidad", text)
        self.assertIn("Usar el pedido", text)

    def test_graphify_is_optional_and_manual(self):
        self.config["packs"].append("graphify")
        initialize(self.config, self.root, fetcher=self.fake)
        target = self.root / "mi-app"
        script = target / ".createapp/setup_graphify.py"
        self.assertTrue(script.exists())
        self.assertFalse((target / ".createapp/tools").exists())
        self.assertNotIn("subprocess.run([\"graphify\", \"install\"", script.read_text())

    def test_concurrent_instruction_edit_is_not_overwritten(self):
        target = self.root / "mi-app"
        target.mkdir(exist_ok=True)
        (target / "AGENTS.md").write_text("old")
        self.config["template"] = "config-only"
        def edit_then_download(repo, source, entry, cache):
            (target / "AGENTS.md").write_text("edited by user")
            return self.fake(repo,source,entry,cache)
        with self.assertRaises(ConfigError): initialize(self.config, self.root, fetcher=edit_then_download)
        self.assertEqual((target / "AGENTS.md").read_text(), "edited by user")
        self.assertFalse((target / ".createapp").exists())

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.available = {"status": "available", "current": "0.2.0", "latest": "0.3.0", "tag": "v0.3.0"}
        connectivity = patch("updates.internet_available", return_value=True)
        connectivity.start()
        self.addCleanup(connectivity.stop)
        answers = patch("builtins.input", return_value="n")
        answers.start()
        self.addCleanup(answers.stop)

    def test_update_check_compares_versions_numerically(self):
        release = {"tag_name": "v0.2.10", "draft": False, "prerelease": False}
        with patch("updates.VERSION", "0.2.9"), patch("urllib.request.urlopen", return_value=BytesIO(json.dumps(release).encode())) as request:
            result = check_for_updates()
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["latest"], "0.2.10")
        self.assertEqual(request.call_args.kwargs["timeout"], 2)
        self.assertEqual(request.call_args.args[0].full_url, "https://api.github.com/repos/Recamm/createapp/releases/latest")

    def test_equal_older_draft_and_prerelease_versions(self):
        cases = [("v0.2.9", False, False, "current"), ("v0.2.8", False, False, "current"), ("v0.3.0", True, False, "unavailable"), ("v0.3.0", False, True, "unavailable"), ("v0.3.0-beta.1", False, False, "unavailable"), ("invalid\ntext", False, False, "unavailable")]
        for tag, draft, prerelease, expected in cases:
            release = {"tag_name": tag, "draft": draft, "prerelease": prerelease}
            with self.subTest(tag=tag, draft=draft, prerelease=prerelease), patch("updates.VERSION", "0.2.9"), patch("urllib.request.urlopen", return_value=BytesIO(json.dumps(release).encode())):
                self.assertEqual(check_for_updates()["status"], expected)

    def test_every_check_queries_github_without_cache(self):
        release = json.dumps({"tag_name": "v0.3.0"}).encode()
        with patch("urllib.request.urlopen", side_effect=lambda *args, **kwargs: BytesIO(release)) as request:
            for attempt in range(3):
                self.assertEqual(check_for_updates()["status"], "available")
            self.assertEqual(request.call_count, 3)
            with patch("updates.VERSION", "0.3.0"):
                self.assertEqual(check_for_updates()["status"], "current")
            self.assertEqual(request.call_count, 4)

    def test_update_check_network_failures_are_silent_and_retried_next_time(self):
        failures = [TimeoutError("offline"), urllib.error.HTTPError("https://api.github.com", 429, "rate limit", {}, None), IncompleteRead(b"partial")]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch("urllib.request.urlopen", side_effect=failure) as request:
                result = check_for_updates()
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(update_message(result), "")
                check_for_updates()
                self.assertEqual(request.call_count, 2)

    def test_malformed_and_oversized_releases_do_not_interrupt_startup(self):
        for payload in (b"not json", b"[]", b"null", b" " * (MAX_RELEASE_BYTES + 1)):
            with self.subTest(size=len(payload)), patch("urllib.request.urlopen", return_value=BytesIO(payload)):
                self.assertEqual(check_for_updates()["status"], "unavailable")

    def test_offline_skips_release_query_and_prompt(self):
        with patch("updates.internet_available", return_value=False), patch("urllib.request.urlopen") as request, patch("builtins.input") as answer, patch("sys.stderr", new_callable=StringIO) as stderr:
            result = check_for_updates()
            self.assertFalse(offer_update(result))
        request.assert_not_called()
        answer.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")

    def test_connectivity_probe_handles_network_failure_and_https_proxy(self):
        with patch("urllib.request.getproxies", return_value={}), patch("socket.create_connection", side_effect=OSError("offline")) as connection:
            self.assertFalse(internet_available())
        connection.assert_called_once_with(("api.github.com", 443), timeout=1)
        with patch("urllib.request.getproxies", return_value={"https": "http://proxy.example:8080"}), patch("socket.create_connection") as connection:
            self.assertTrue(internet_available())
        connection.assert_called_once_with(("proxy.example", 8080), timeout=1)

    def test_current_or_unavailable_release_is_silent(self):
        for status in ("current", "unavailable"):
            result = dict(self.available, status=status)
            self.assertEqual(update_message(result), "")
            with patch("builtins.input") as answer, patch("updates.install_update") as install, patch("sys.stderr", new_callable=StringIO) as stderr:
                self.assertFalse(offer_update(result))
            answer.assert_not_called()
            install.assert_not_called()
            self.assertEqual(stderr.getvalue(), "")

    def test_terminal_startup_announces_updates(self):
        with patch("sys.argv", ["createapp", str(self.root)]), patch("sys.stdin.isatty", return_value=True), patch.dict("os.environ", {"CREATEAPP_NO_UPDATE_CHECK": "0"}), patch("createapp.check_for_updates", return_value=self.available) as check, patch("terminal.run") as run, patch("sys.stderr", new_callable=StringIO) as stderr:
            main()
        check.assert_called_once_with()
        run.assert_called_once()
        self.assertIn("0.3.0 disponible", stderr.getvalue())

    def test_ui_startup_announces_updates(self):
        with patch("sys.argv", ["createapp", str(self.root), "--ui", "--no-browser"]), patch.dict("os.environ", {"CREATEAPP_NO_UPDATE_CHECK": "0"}), patch("createapp.check_for_updates", return_value=self.available) as check, patch("createapp.AppServer") as server, patch("sys.stdout", new_callable=StringIO), patch("sys.stderr", new_callable=StringIO) as stderr:
            server.return_value.base_url = "http://127.0.0.1:12345"
            server.return_value.token = "fixture"
            main()
        check.assert_called_once_with()
        server.return_value.serve_forever.assert_called_once()
        server.return_value.server_close.assert_called_once()
        self.assertIn("0.3.0 disponible", stderr.getvalue())

    def test_explicit_update_check_queries_once_and_ignores_old_opt_out(self):
        with patch("sys.argv", ["createapp", "--check-updates"]), patch.dict("os.environ", {"CREATEAPP_NO_UPDATE_CHECK": "1"}), patch("createapp.check_for_updates", return_value=self.available) as check, patch("sys.stdout", new_callable=StringIO) as stdout, patch("sys.stderr", new_callable=StringIO) as stderr:
            main()
        check.assert_called_once_with()
        self.assertIn("0.3.0 disponible", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")

    def test_accepting_update_installs_before_running_original_command(self):
        with patch("sys.argv", ["createapp", str(self.root)]), patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="si"), patch("createapp.check_for_updates", return_value=self.available) as check, patch("updates.install_update") as install, patch("terminal.run") as run, patch("sys.stdout", new_callable=StringIO) as stdout, patch("sys.stderr", new_callable=StringIO) as stderr:
            main()
        check.assert_called_once_with()
        install.assert_called_once_with(self.available)
        run.assert_not_called()
        self.assertIn("[s/N]", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")

    def test_declining_or_eof_does_not_download_or_install(self):
        for answer in ("", "n", "no", EOFError()):
            with self.subTest(answer=answer), patch("sys.stdin.isatty", return_value=True), patch("builtins.input", **({"side_effect": answer} if isinstance(answer, Exception) else {"return_value": answer})), patch("updates.install_update") as install, patch("urllib.request.urlopen") as download, patch("sys.stderr", new_callable=StringIO):
                self.assertFalse(offer_update(self.available))
            install.assert_not_called()
            download.assert_not_called()

    def test_control_c_at_confirmation_cancels_the_command(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=KeyboardInterrupt()), patch("updates.install_update") as install, patch("sys.stderr", new_callable=StringIO):
            self.assertTrue(offer_update(self.available))
        install.assert_not_called()

    def test_noninteractive_preview_warns_without_consuming_input_or_changing_json(self):
        config = self.root / "config.json"
        config.write_text(json.dumps(DEFAULTS), encoding="utf-8")
        with patch("sys.argv", ["createapp", str(self.root), "--preview", str(config)]), patch("sys.stdin.isatty", return_value=False), patch("builtins.input") as answer, patch("createapp.check_for_updates", return_value=self.available), patch("createapp.preview", return_value={"ok": True}), patch("updates.install_update") as install, patch("sys.stdout", new_callable=StringIO) as stdout, patch("sys.stderr", new_callable=StringIO) as stderr:
            main()
        self.assertEqual(json.loads(stdout.getvalue()), {"ok": True})
        self.assertIn("0.3.0 disponible", stderr.getvalue())
        answer.assert_not_called()
        install.assert_not_called()

    def test_failed_install_keeps_original_command_available(self):
        with patch("sys.argv", ["createapp", str(self.root)]), patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="s"), patch("createapp.check_for_updates", return_value=self.available), patch("updates.install_update", side_effect=OSError("download failed")), patch("terminal.run") as run, patch("sys.stderr", new_callable=StringIO) as stderr:
            main()
        run.assert_called_once()
        self.assertIn("version actual", stderr.getvalue())

    def test_posix_install_uses_pinned_release_and_cleans_up(self):
        for platform in ("linux", "darwin"):
            folder = self.root / "download"
            folder.mkdir()
            def verify_installer(command, **kwargs):
                self.assertEqual(command[0], "sh")
                self.assertEqual(Path(command[1]).read_bytes(), b"#!/bin/sh\nexit 0\n")
                self.assertEqual(kwargs["env"]["CREATEAPP_VERSION"], "v0.3.0")
                self.assertEqual(kwargs["env"]["CREATEAPP_REPO"], "Recamm/createapp")
                self.assertEqual(kwargs["env"]["CREATEAPP_NO_LAUNCH"], "1")
                self.assertEqual(kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
                self.assertTrue(kwargs["check"])
            with self.subTest(platform=platform), patch("updates.sys.platform", platform), patch("updates.tempfile.mkdtemp", return_value=str(folder)), patch("urllib.request.urlopen", return_value=BytesIO(b"#!/bin/sh\nexit 0\n")) as download, patch("updates.subprocess.run", side_effect=verify_installer) as run, patch("updates.subprocess.Popen") as launch:
                install_update(self.available)
            self.assertEqual(download.call_args.args[0].full_url, "https://github.com/Recamm/createapp/releases/download/v0.3.0/install.sh")
            run.assert_called_once()
            launch.assert_not_called()
            self.assertFalse(folder.exists())

    def test_windows_install_launches_worker_that_waits_for_current_process(self):
        folder = self.root / "download"
        folder.mkdir()
        with patch("updates.sys.platform", "win32"), patch("updates.tempfile.mkdtemp", return_value=str(folder)), patch("urllib.request.urlopen", return_value=BytesIO(b"Write-Host 'fixture'")) as download, patch("updates.subprocess.Popen") as launch, patch("updates.subprocess.run") as run:
            install_update(self.available)
        self.assertEqual(download.call_args.args[0].full_url, "https://github.com/Recamm/createapp/releases/download/v0.3.0/install.ps1")
        command = launch.call_args.args[0]
        self.assertTrue(command[0].endswith("powershell.exe"))
        self.assertEqual(command[1:3], ["-NoProfile", "-EncodedCommand"])
        worker = base64.b64decode(command[3]).decode("utf-16le")
        self.assertIn("Wait-Process", worker)
        self.assertIn("CREATEAPP_UPDATE_PID", worker)
        self.assertIn("-NoLaunch", worker)
        self.assertIn("finally", worker)
        self.assertIn("Remove-Item -LiteralPath", worker)
        self.assertNotIn("ExecutionPolicy", worker)
        environment = launch.call_args.kwargs["env"]
        self.assertTrue(environment["CREATEAPP_UPDATE_PID"].isdigit())
        self.assertEqual(environment["CREATEAPP_VERSION"], "v0.3.0")
        self.assertEqual(Path(environment["CREATEAPP_UPDATE_SCRIPT"]).read_bytes(), b"Write-Host 'fixture'")
        self.assertEqual(launch.call_args.kwargs["creationflags"], 0x00000010)
        run.assert_not_called()

    def test_failed_windows_launch_cleans_up_download(self):
        folder = self.root / "download"
        folder.mkdir()
        with patch("updates.sys.platform", "win32"), patch("updates.tempfile.mkdtemp", return_value=str(folder)), patch("urllib.request.urlopen", return_value=BytesIO(b"fixture")), patch("updates.subprocess.Popen", side_effect=OSError("cannot launch")), self.assertRaises(OSError):
            install_update(self.available)
        self.assertFalse(folder.exists())

    def test_failed_posix_installer_cleans_up_download(self):
        folder = self.root / "download"
        folder.mkdir()
        with patch("updates.sys.platform", "linux"), patch("updates.tempfile.mkdtemp", return_value=str(folder)), patch("urllib.request.urlopen", return_value=BytesIO(b"fixture")), patch("updates.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["sh"])), self.assertRaises(subprocess.CalledProcessError):
            install_update(self.available)
        self.assertFalse(folder.exists())

    def test_invalid_installer_releases_are_rejected_before_download(self):
        for changes in ({"tag": "v0.3.0;command"}, {"tag": "v0.4.0"}, {"tag": None}, {"status": "current"}):
            with self.subTest(changes=changes), patch("urllib.request.urlopen") as download, self.assertRaises(ValueError):
                install_update(dict(self.available, **changes))
            download.assert_not_called()

    def test_empty_or_oversized_installers_never_execute(self):
        for payload in (b"", b" " * (128 * 1024 + 1)):
            with self.subTest(size=len(payload)), patch("urllib.request.urlopen", return_value=BytesIO(payload)), patch("updates.subprocess.Popen") as launch, patch("updates.subprocess.run") as run, self.assertRaises(ValueError):
                install_update(self.available)
            launch.assert_not_called()
            run.assert_not_called()

    def test_doctor_prefetch_ux_search_and_invalid_commands_also_check(self):
        current = dict(self.available, status="current")
        for arguments in (["--doctor"], ["--prefetch"], ["--ux-search", "query"], ["--invalid-option"]):
            with self.subTest(arguments=arguments), patch("sys.argv", ["createapp", str(self.root), *arguments]), patch("createapp.check_for_updates", return_value=current) as check, patch("doctor.inspect", return_value={}), patch("tooling.ux_search"), patch("createapp.LOCK", {"sources": {}}), patch("sys.stdout", new_callable=StringIO), patch("sys.stderr", new_callable=StringIO):
                if arguments == ["--invalid-option"]:
                    with self.assertRaises(SystemExit) as exit:
                        main()
                    self.assertEqual(exit.exception.code, 2)
                else:
                    main()
                check.assert_called_once_with()

    def test_help_version_and_json_commands_check_updates_every_time(self):
        current = dict(self.available, status="current")
        for argument in ("--help", "--version"):
            with self.subTest(argument=argument), patch("sys.argv", ["createapp", argument]), patch("createapp.check_for_updates", return_value=current) as check, patch("sys.stdout", new_callable=StringIO), self.assertRaises(SystemExit) as exit:
                main()
            self.assertEqual(exit.exception.code, 0)
            check.assert_called_once_with()
        config = self.root / "config.json"
        config.write_text(json.dumps(DEFAULTS), encoding="utf-8")
        for argument, operation in (("--preview", "preview"), ("--apply", "initialize")):
            with self.subTest(argument=argument), patch("sys.argv", ["createapp", str(self.root), argument, str(config)]), patch("createapp.check_for_updates", return_value=current) as check, patch("createapp." + operation, return_value={"ok": True}), patch("sys.stdout", new_callable=StringIO) as stdout, patch("sys.stderr", new_callable=StringIO) as stderr:
                main()
            check.assert_called_once_with()
            self.assertEqual(json.loads(stdout.getvalue()), {"ok": True})
            self.assertEqual(stderr.getvalue(), "")

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = AppServer(("127.0.0.1",0),Path(self.temp.name))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()

    def request(self,path,body=None,token=True,origin=None):
        headers={"Content-Type":"application/json"}
        if token: headers["X-CreateApp-Token"]=self.server.token
        if origin: headers["Origin"]=origin
        req=urllib.request.Request(self.server.base_url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        return urllib.request.urlopen(req,timeout=5)

    def test_auth_and_cross_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as cm: self.request("/api/catalog",token=False)
        self.assertEqual(cm.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError) as cm: self.request("/api/preview",{},origin="https://example.com")
        self.assertEqual(cm.exception.code,403)

    def test_incremental_catalog_preview_and_stale_request(self):
        initialize(DEFAULTS, self.server.workspace, fetcher=lambda *args: b"fixture")
        with self.request("/api/catalog") as response: catalog = json.load(response)
        self.assertIn("workflow", catalog["installation"]["installed"])
        self.assertIn("find-skills", catalog["installation"]["available"])
        with self.request("/api/additions/preview", {"skills": ["find-skills"]}) as response: planned = json.load(response)
        self.assertEqual(planned["roles"], ["find-skills"])
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/additions/initialize", {"skills": ["find-skills"], "config_hash": "stale"})
        self.assertEqual(error.exception.code, 400)
        self.assertFalse((self.server.workspace / ".agents/skills/ca-find-skills").exists())

    def test_preview_and_stale_hash_never_writes(self):
        with self.request("/api/preview",DEFAULTS) as res: p=json.load(res)
        self.assertIn("workflow",p["roles"])
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request("/api/initialize",{"config":DEFAULTS,"config_hash":"stale"})
        self.assertEqual(cm.exception.code,400)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])

if __name__ == "__main__": unittest.main()

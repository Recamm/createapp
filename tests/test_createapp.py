import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import DEFAULTS, roles_for
from createapp import AppServer
from engine import ConfigError, blob_hash, fetch_blob, initialize, preview, validate
from policy import policy, wrapper

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

    def test_preview_and_stale_hash_never_writes(self):
        with self.request("/api/preview",DEFAULTS) as res: p=json.load(res)
        self.assertIn("workflow",p["roles"])
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request("/api/initialize",{"config":DEFAULTS,"config_hash":"stale"})
        self.assertEqual(cm.exception.code,400)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])

if __name__ == "__main__": unittest.main()

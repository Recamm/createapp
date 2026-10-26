import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import DEFAULTS, roles_for
from engine import ConfigError, initialize, preview, fetch_blob, LOCK
from terminal import collect, run
from runtime import project_defaults

class DefaultsPrompts:
    def __init__(self): self.calls = []
    def ask(self, kind, message, choices=None, default=None):
        self.calls.append((kind,message,choices,default))
        return copy.deepcopy(default)

class NativeConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def fake(self, repo, source, entry, cache): return b"fixture"

    def test_existing_project_only(self):
        with self.assertRaises(ConfigError): preview(DEFAULTS,self.project/'missing')
        with self.assertRaises(ConfigError): preview(dict(DEFAULTS,template='react-vite'),self.project)
        self.assertEqual(DEFAULTS['template'],'config-only')
        self.assertEqual(DEFAULTS['directory'],'.')

    def test_multiple_agents_and_one_contract(self):
        c = dict(DEFAULTS,agents=['copilot','codex','claude','cursor'])
        initialize(c,self.project,fetcher=self.fake)
        for name in ['AGENTS.md','CLAUDE.md','.github/copilot-instructions.md','.cursor/rules/createapp.mdc','.agents/skills/ca-workflow/SKILL.md','.claude/skills/ca-workflow/SKILL.md']:
            self.assertTrue((self.project/name).is_file(),name)
        self.assertEqual(len(list(self.project.rglob('POLICY.md'))),1)

    def test_individual_skills_and_required_coordinator(self):
        c=dict(DEFAULTS,skills=['workflow','simplicity'])
        self.assertEqual(set(preview(c,self.project)['roles']),{'workflow','simplicity'})
        with self.assertRaises(ConfigError): preview(dict(DEFAULTS,skills=['simplicity']),self.project)
        self.assertEqual(preview(dict(DEFAULTS,coordinator='simple',skills=[]),self.project)['roles'],[])

    def test_default_wizard_and_cancellation(self):
        prompts=DefaultsPrompts()
        c=collect(self.project,prompts)
        self.assertNotIn('matt',c['packs'])
        self.assertNotIn('graphify',c['packs'])
        self.assertEqual(c['coordinator'],'superpowers')
        self.assertIsNone(run(self.project,prompts=DefaultsPrompts()))
        self.assertEqual(list(self.project.iterdir()),[])

    def test_preset_and_advanced_selection(self):
        class Custom(DefaultsPrompts):
            def ask(self,kind,message,choices=None,default=None):
                if message.startswith('Forma'): return 'rigorous'
                if message.startswith('Asistentes'): return ['codex','claude']
                if message.startswith('Asistente principal'): return 'codex'
                return super().ask(kind,message,choices,default)
        c=collect(self.project,Custom())
        self.assertEqual(c['testing'],'strict')
        self.assertEqual(c['autonomy'],'guided')
        self.assertEqual(c['agents'],['codex','claude'])
        self.assertEqual(c['agent'],'codex')

    def test_bundled_sources_work_without_network(self):
        repo='DietrichGebert/ponytail';source=LOCK['sources'][repo];entry=source['files'][0]
        with patch('urllib.request.urlopen',side_effect=AssertionError('network should not be used')):
            blob=fetch_blob(repo,source,entry,self.project/'empty-cache')
        self.assertTrue(blob)
        self.assertFalse((self.project/'empty-cache').exists())

    def test_original_project_is_unchanged(self):
        original={'package.json':'{"dependencies":{"react":"19"}}','README.md':'my readme','START_HERE.md':'my guide','src/app.txt':'application'}
        for name,text in original.items():
            p=self.project/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        initialize(DEFAULTS,self.project,fetcher=self.fake)
        for name,text in original.items(): self.assertEqual((self.project/name).read_text(),text)

if __name__=='__main__': unittest.main()

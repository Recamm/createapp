import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import hashlib

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipIf(os.name == 'nt', 'POSIX installer; Windows syntax is checked on its native runner.')
class InstallerTests(unittest.TestCase):
    def exercise(self, corrupt=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fixtures=root/'fixtures';fixtures.mkdir();shims=root/'shims';shims.mkdir()
            asset=fixtures/'createapp-linux-x64.tar.gz'
            with tarfile.open(asset,'w:gz') as archive:
                data=b'#!/bin/sh\nprintf "CreateApp test\\n"\n'
                info=tarfile.TarInfo('createapp');info.size=len(data);info.mode=0o755;archive.addfile(info,io.BytesIO(data))
            checksum='0'*64 if corrupt else hashlib.sha256(asset.read_bytes()).hexdigest()
            (fixtures/'SHA256SUMS').write_text(checksum+'  '+asset.name+'\n')
            curl=shims/'curl'
            curl.write_text('''#!/bin/sh
url=; dest=
while [ $# -gt 0 ]; do
 case "$1" in https://*) url=$1;; --output) shift; dest=$1;; esac
 shift
done
cp "$CREATEAPP_TEST_FIXTURES/${url##*/}" "$dest"
''');curl.chmod(0o755)
            uname=shims/'uname';uname.write_text('#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo x86_64;; esac\n');uname.chmod(0o755)
            env=dict(os.environ,PATH=str(shims)+os.pathsep+os.environ.get('PATH',''),CREATEAPP_BIN_DIR=str(root/'bin'),CREATEAPP_NO_LAUNCH='1',CREATEAPP_TEST_FIXTURES=str(fixtures),XDG_DATA_HOME=str(root/'data'))
            result=subprocess.run(['sh',str(ROOT/'install.sh')],env=env,capture_output=True,text=True)
            if corrupt:
                self.assertNotEqual(result.returncode,0)
                self.assertFalse((root/'bin/createapp').exists())
            else:
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertTrue((root/'bin/createapp').is_file())
                self.assertIn('CreateApp test',result.stdout)

    def test_install_from_mock_release(self): self.exercise()
    def test_corrupt_archive_is_not_installed(self): self.exercise(corrupt=True)

if __name__=='__main__': unittest.main()

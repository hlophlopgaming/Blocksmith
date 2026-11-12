# SPDX-License-Identifier: GPL-3.0-or-later
"""Run with ordinary Python: validates the real Blender CLI/export boundary."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='blocksmith-cli-guard-') as folder:
    root=Path(folder); spec=root/'input.json'; out=root/'result'
    data={'version':1,'objects':[{'name':'Left','shape':'BLOCK','position':[0,0,0]},
                                {'name':'Right','shape':'BLOCK','position':[2,0,0]}]}
    spec.write_text(json.dumps(data))
    cmd=[sys.executable,str(ROOT/'tools/levelgen.py'),'generate',str(spec),'--out-dir',str(out)]
    good=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
    assert good.returncode==0,(good.stdout,good.stderr)
    assert json.loads(good.stdout)['ok']
    original={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('level.glb','level.blend')}
    data['objects'][1]['position']=[1,0,0]; spec.write_text(json.dumps(data))
    bad=subprocess.run(cmd+['--overwrite'],capture_output=True,text=True,timeout=90)
    assert bad.returncode==1 and not bad.stdout,(bad.stdout,bad.stderr)
    error=json.loads(bad.stderr)
    assert not error['ok'] and 'Left' in error['error'] and 'Right' in error['error'],error
    assert original=={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in original}
print('PASS: CLI accepts touching faces, rejects intersecting named objects and preserves previous exports')

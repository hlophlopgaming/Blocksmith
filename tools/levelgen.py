#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Agent-friendly Blender level generation; only the Python standard library is required."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from level_spec import load, schema, SHAPES, PRESETS

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('presets',help='Print editable module presets and defaults as JSON')
    sub.add_parser('shapes',help='Print valid shape identifiers as JSON')
    sub.add_parser('schema',help='Print the JSON Schema for agent/tool integration')
    sub.add_parser('example',help='Print a complete example level specification')
    validate=sub.add_parser('validate',help='Validate JSON without starting Blender')
    validate.add_argument('spec',type=Path)
    generate=sub.add_parser('generate',help='Generate level.blend, level.glb and report.json')
    generate.add_argument('spec',type=Path)
    generate.add_argument('--out-dir',type=Path,required=True)
    generate.add_argument('--blender',default='blender',help='Blender 5+ executable')
    generate.add_argument('--overwrite',action='store_true',help='Replace previously generated output files')
    generate.add_argument('--timeout',type=int,default=180,help='Blender time limit in seconds')
    args=parser.parse_args()
    try:
        if args.command=='presets': return {'ok':True,'presets':[{'id':p[0],'label':p[1],'group':p[2],'shape':p[3],'params':p[4]} for p in PRESETS]}
        if args.command=='schema': return schema()
        if args.command=='shapes': return {'ok':True,'shapes':SHAPES}
        if args.command=='example': return json.loads((ROOT/'examples/courtyard.json').read_text())
        spec=load(args.spec)
        if args.command=='validate': return {'ok':True,'objects':len(spec['objects']),'version':1}
        if args.timeout<1: raise ValueError('--timeout must be positive')
        executable=shutil.which(args.blender)
        if not executable: raise ValueError('Blender executable not found: '+args.blender)
        out=args.out_dir.expanduser().resolve()
        names=('level.blend','level.glb','level.spec.json','report.json','blender.log')
        if not args.overwrite and any((out/name).exists() for name in names):
            raise ValueError('Output already exists; use a new directory or --overwrite')
        out.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.blocksmith-',dir=out) as folder:
            stage=Path(folder)
            (stage/'spec.json').write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8')
            cmd=[executable,'--background','-noaudio','--factory-startup','--python-exit-code','1',
                 '--python',str(ROOT/'tools/blender_generate.py'),'--',str(stage),str(out)]
            with (stage/'blender.log').open('w',encoding='utf-8') as log:
                try:
                    result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,
                                          env={**os.environ,'PYTHONUNBUFFERED':'1'},
                                          timeout=args.timeout,check=False)
                except subprocess.TimeoutExpired:
                    log.flush()
                    shutil.copyfile(stage/'blender.log',out/'blender.log')
                    raise RuntimeError(f'Blender exceeded {args.timeout}s; see {out/"blender.log"}')
            if result.returncode or not (stage/'report.json').exists():
                shutil.copyfile(stage/'blender.log',out/'blender.log')
                detail=json.loads((stage/'error.json').read_text())['error'] if (stage/'error.json').exists() else f'Blender exited with {result.returncode}'
                raise RuntimeError(f'{detail}; see {out/"blender.log"}')
            shutil.copyfile(stage/'spec.json',stage/'level.spec.json')
            report=json.loads((stage/'report.json').read_text())
            for name in names: os.replace(stage/name,out/name)
        return report
    except (ValueError,OSError,RuntimeError,RecursionError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return None


if __name__=='__main__':
    result=main()
    if result is None: sys.exit(1)
    print(json.dumps(result,ensure_ascii=False,indent=2))

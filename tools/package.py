#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the installable Blender extension using only the Python standard library."""
import argparse
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]


def package(out_dir):
    addon=ROOT/'blocksmith'
    version=re.search(r'^version = "([0-9.]+)"$',(addon/'blender_manifest.toml').read_text(),re.M).group(1)
    out_dir.mkdir(parents=True,exist_ok=True)
    path=out_dir/f'blocksmith-{version}.zip'
    with ZipFile(path,'w',ZIP_DEFLATED) as archive:
        for file in sorted(addon.rglob('*')):
            relative=file.relative_to(addon)
            if file.is_file() and not any(p.startswith('.') or p=='__pycache__' for p in relative.parts) and file.suffix!='.pyc':
                archive.write(file,relative)
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',type=Path,default=ROOT/'dist')
    print(package(parser.parse_args().out_dir))

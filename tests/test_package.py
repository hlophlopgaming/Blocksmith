# SPDX-License-Identifier: GPL-3.0-or-later
import ast
from pathlib import Path
import re
import sys
import tempfile
import unittest
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from package import ROOT, package


class PackageTests(unittest.TestCase):
    def test_installable_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            path=package(Path(folder))
            with ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                names=archive.namelist()
                self.assertIn('blender_manifest.toml',names)
                self.assertIn('__init__.py',names)
                self.assertIn('LICENSE',names)
                self.assertIn('assets/kenney/License.txt',names)
                self.assertIn('assets/kenney/SOURCE.txt',names)
                self.assertEqual(sum(n.startswith('assets/previews/') and n.endswith('.png') for n in names),32)
                self.assertEqual(sum(n.startswith('assets/kenney/PNG/') and n.endswith('.png') for n in names),78)
                self.assertFalse(any('__pycache__' in n or n.endswith('.pyc') or Path(n).is_absolute() for n in names))
                manifest=archive.read('blender_manifest.toml').decode()
                version=re.search(r'^version = "([0-9.]+)"$',manifest,re.M).group(1)
                self.assertEqual(path.name,f'blocksmith-{version}.zip')
                source=ast.parse(archive.read('__init__.py').decode())
                info=next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign) and
                          any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets))
                self.assertEqual(info['version'],tuple(map(int,version.split('.'))))
                self.assertIn('SPDX:GPL-3.0-or-later',manifest)
                self.assertEqual(archive.read('LICENSE'),(ROOT/'LICENSE').read_bytes())


if __name__=='__main__': unittest.main()

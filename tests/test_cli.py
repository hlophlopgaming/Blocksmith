# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from level_spec import validate, load, resolve

ROOT=Path(__file__).resolve().parents[1]

class SpecificationTests(unittest.TestCase):
    def test_contour_shapes_validate_boundaries(self):
        floor={'name':'Outline','shape':'POLY_FLOOR','contours':[[[0,0],[5,0],[5,5],[0,5]],[[1,1],[2,1],[2,2],[1,2]]]}
        validate({'version':1,'objects':[floor]})
        for change in ({'contours':[[[0,0],[2,2],[0,2],[2,0]]]}, {'shape':'FLOOR'}):
            with self.assertRaises(ValueError):validate({'version':1,'objects':[{**floor,**change}]})
        floor.pop('contours')
        with self.assertRaises(ValueError):validate({'version':1,'objects':[floor]})

    def setUp(self):
        self.spec={'version':1,'objects':[{'name':'Floor','shape':'FLOOR','params':{'width':10,'depth':8,'height':.2}}]}

    def test_preset_and_material(self):
        obj={'name':'Arcade','preset':'arcade','params':{'count':3},'material':{'palette':'Orange','pattern':'13','tile_size':2}}
        validate({'version':1,'objects':[obj]})
        self.assertEqual(resolve(obj)['shape'],'ARCH')
        self.assertEqual(resolve(obj)['params']['count'],3)
        self.assertEqual(resolve(obj)['params']['width'],10)
        obj['material']['pattern']='../bad'
        with self.assertRaises(ValueError): validate({'version':1,'objects':[obj]})

    def test_example_valid(self):
        self.assertEqual(len(load(ROOT/'examples/courtyard.json')['objects']),17)

    def test_signed_wall_joints(self):
        from level_spec import schema
        obj={'name':'Joined wall','shape':'WALL','params':{'miter_start':-.2,'miter_end':.2}}
        self.assertIsNotNone(validate({'version':1,'objects':[obj]}))
        self.assertEqual(schema()['properties']['objects']['items']['properties']['params']['properties']['miter_start']['minimum'],-1000)
        for invalid in (float('nan'),-1001,True,'0.2'):
            obj['params']['miter_start']=invalid
            with self.assertRaises(ValueError): validate({'version':1,'objects':[obj]})

    def test_invalid_values(self):
        for key,value in [('width',float('nan')),('width',10**500),('steps',True),('auto_steps',1),('height',-1),('unknown',3)]:
            with self.subTest(key=key,value=str(value)[:30]):
                data=copy.deepcopy(self.spec); data['objects'][0]['params']={key:value}
                with self.assertRaises(ValueError): validate(data)

    def test_room_opening(self):
        from level_spec import schema
        obj={'name':'Room','shape':'ROOM','params':{'opening':'DOOR','room_wall':'RIGHT','open_width':1.2,'offset':.4}}
        self.assertIsNotNone(validate({'version':1,'objects':[obj]}))
        self.assertEqual(tuple(schema()['properties']['objects']['items']['properties']['params']['properties']['room_wall']['enum']),('FRONT','BACK','LEFT','RIGHT'))
        obj['params']['room_wall']='CEILING'
        with self.assertRaises(ValueError): validate({'version':1,'objects':[obj]})

    def test_duplicate_name_and_unknown_shape(self):
        data=copy.deepcopy(self.spec); data['objects']*=2
        with self.assertRaisesRegex(ValueError,'duplicate name'): validate(data)
        data=copy.deepcopy(self.spec); data['objects'][0]['shape']='PYTHON'
        with self.assertRaisesRegex(ValueError,'unknown shape'): validate(data)

    def test_cut_validation(self):
        data=copy.deepcopy(self.spec); data['cuts']=[{'target':'Floor','cutter':'Floor'}]
        with self.assertRaisesRegex(ValueError,'itself'): validate(data)
        data['cuts']=[{'target':'Floor','cutter':'missing'}]
        with self.assertRaisesRegex(ValueError,'existing objects'): validate(data)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.json'; path.write_text('{"version": 1, "version": 1}')
            with self.assertRaisesRegex(ValueError,'duplicate JSON key'): load(path)

    def test_cli_machine_output(self):
        result=subprocess.run([sys.executable,str(ROOT/'tools/levelgen.py'),'shapes'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
        self.assertIn('ROOM',json.loads(result.stdout)['shapes'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.json'; path.write_text('{}')
            result=subprocess.run([sys.executable,str(ROOT/'tools/levelgen.py'),'validate',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,1); self.assertEqual(result.stdout,'')
            self.assertFalse(json.loads(result.stderr)['ok'])

if __name__=='__main__': unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise Blender's real translation lookup and a live language change."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import blocksmith as bs
from blocksmith.translations import tr, MESSAGES
bs.register()
keys={row[0] for row in MESSAGES}
for group in (bpy.context.scene.bs,bpy.context.active_object.bs):
    for prop in group.bl_rna.properties:
        if prop.identifier in {'rna_type','name'}: continue
        assert prop.name in keys,prop.name
        if prop.type=='ENUM':
            for item in prop.enum_items:
                assert item.name in keys or item.name in {'X','Y','Z'},item.name
view=bpy.context.preferences.view
view.use_translate_interface=True
view.use_translate_tooltips=True
expected={'en_US':'Ignore Blocksmith Rules','ru_RU':'Игнорировать правила Blocksmith',
          'es':'Ignorar reglas de Blocksmith','fr_FR':'Ignorer les règles de Blocksmith',
          'de_DE':'Blocksmith-Regeln ignorieren'}
for locale,label in expected.items():
    view.language=locale
    actual=tr('Ignore Blocksmith Rules')
    print(locale,bpy.app.translations.locale,actual)
    assert actual==label,(locale,actual,label)
view.language='en_US'
bs.unregister(); bs.register(); bs.unregister()
print('PASS: five interface languages, live locale changes and clean re-registration')

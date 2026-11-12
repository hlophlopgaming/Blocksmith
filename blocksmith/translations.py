# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender-native interface translations; English source, four translated locales."""
import json
from pathlib import Path
import bpy
from bpy.app.translations import pgettext_iface as tr

MESSAGES=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
TRANSLATIONS={locale:{(context,row[0]):row[column] for row in MESSAGES for context in ('*','Operator')}
              for column,locale in enumerate(('ru_RU','es','fr_FR','de_DE'),1)}


def register():
    bpy.app.translations.register(__package__,TRANSLATIONS)


def unregister():
    bpy.app.translations.unregister(__package__)

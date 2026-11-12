# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
from string import Formatter
import unittest

CATALOG=Path(__file__).resolve().parents[1]/'blocksmith/translations.json'


class TranslationTests(unittest.TestCase):
    def test_catalog_covers_all_languages_and_preserves_placeholders(self):
        rows=json.loads(CATALOG.read_text(encoding='utf-8'))
        self.assertEqual(len({row[0] for row in rows}),len(rows))
        for row in rows:
            self.assertEqual(len(row),5,row)
            expected=sorted((field,spec,conv) for _,field,spec,conv in Formatter().parse(row[0]) if field is not None)
            for text in row:
                self.assertTrue(text.strip(),row)
                actual=sorted((field,spec,conv) for _,field,spec,conv in Formatter().parse(text) if field is not None)
                self.assertEqual(expected,actual,row)
        self.assertIn('Ignore Blocksmith Rules',{row[0] for row in rows})


if __name__=='__main__': unittest.main()

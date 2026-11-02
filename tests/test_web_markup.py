"""Catch missing HTML targets before account screens fail at runtime."""
import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class IDs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
    def handle_starttag(self, tag, attrs):
        self.ids.extend(value for name,value in attrs if name=='id')

class WebMarkupTests(unittest.TestCase):
    def test_all_javascript_targets_exist_once(self):
        parser=IDs()
        parser.feed((ROOT/'web/index.html').read_text(encoding='utf-8'))
        counts=Counter(parser.ids)
        self.assertEqual([key for key,value in counts.items() if value!=1],[])
        script=(ROOT/'web/app.js').read_text(encoding='utf-8')
        targets=set(re.findall(r"\$\(['\"]([^'\"]+)['\"]\)",script))
        self.assertEqual(sorted(targets-set(counts)),[])
        for target in ('question-suggestions','role-introduction','signed-in-as','user-name','user-role'):
            self.assertEqual(counts[target],1)

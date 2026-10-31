import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.authorization import can_read, has_company_access
from src.retrieval import build_access_filter

class CompanyAccessTests(unittest.TestCase):
    def test_explicit_ceo_access_and_other_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'policy.json'
            with patch('src.authorization.workspace_path',return_value=path):
                ceo={'user_id':'Dhanesh','role':'CEO','department':'Executive','clearance':3}
                engineering={'department':'Engineering','clearance':2,'allowed_roles':[]}
                self.assertFalse(can_read(ceo,engineering))
                path.write_text(json.dumps({'ceo_company_access':True}))
                self.assertTrue(can_read(ceo,engineering))
                self.assertEqual(len(build_access_filter(ceo).must),1)
                self.assertFalse(can_read(ceo,{**engineering,'clearance':True}))
                for role,dept,clearance in [('HR Manager','HR',2),('Intern','Engineering',0)]:
                    user={'user_id':'other','role':role,'department':dept,'clearance':clearance}
                    self.assertFalse(has_company_access(user))
                    self.assertFalse(can_read(user,engineering))
                    self.assertEqual(len(build_access_filter(user).must),2)
                for invalid in ('{}','null','{"ceo_company_access": 1}','{"ceo_company_access": false}','broken'):
                    path.write_text(invalid)
                    self.assertFalse(has_company_access(ceo))

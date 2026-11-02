import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from src import user_admin, revocation, credentials, authentication
from src.issue_token import issue_token

class UserAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'data').mkdir()
        self.user={'user_id':'Worker','role':'Engineer','department':'Engineering','clearance':2}
        self.path=self.root/'data/users.json';self.path.write_text(json.dumps([self.user]))
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for module in (user_admin,revocation):
            self.stack.enter_context(patch.object(module,'workspace_path',side_effect=lambda p:self.root/p))
        self.stack.enter_context(patch.object(credentials,'CREDENTIALS_DIR',self.root/'passwords'))
        self.stack.enter_context(patch.object(user_admin,'is_admin',side_effect=lambda uid:uid=='Owner'))
        self.stack.enter_context(patch.object(user_admin,'load_users',side_effect=lambda:({u['user_id']:u for u in json.loads(self.path.read_text())},[])))
        self.audit=self.stack.enter_context(patch.object(user_admin,'write_audit_entry'))
        self.key=self.root/'key'

    def test_reset_revokes_old_token_and_changes_password(self):
        old=issue_token('Worker',now=100,key_path=self.key)
        with patch.object(revocation.time,'time',return_value=150):
            user_admin.change('Owner',{'action':'reset','user_id':'Worker','password':'Reset test 2026!'})
        self.assertEqual(authentication.authenticate(old,now=151,key_path=self.key)[1],'revoked')
        new=issue_token('Worker',now=151,key_path=self.key)
        self.assertEqual(authentication.authenticate(new,now=152,key_path=self.key),('Worker',None))
        self.assertTrue(credentials.check_credentials('Worker','Reset test 2026!'))
        revocation.revoke_token(new)
        self.assertEqual(authentication.authenticate(new,now=152,key_path=self.key)[1],'revoked')

    def test_permissions_and_bad_password_leave_users_unchanged(self):
        before=self.path.read_bytes()
        with self.assertRaises(PermissionError):user_admin.change('Worker',{'action':'disable','user_id':'Worker'})
        with self.assertRaises(ValueError):user_admin.change('Owner',{'action':'reset','user_id':'Worker','password':'ab'})
        self.assertEqual(self.path.read_bytes(),before)
        self.audit.assert_not_called()

    def test_create_update_disable(self):
        user_admin.change('Owner',{'action':'create','user_id':'New','role':'Intern','department':'Engineering','clearance':0,'password':'Create test 2026!'})
        self.assertTrue(credentials.check_credentials('New','Create test 2026!'))
        user_admin.change('Owner',{'action':'update','user_id':'New','role':'Engineer','department':'Engineering','clearance':2})
        self.assertEqual(json.loads(self.path.read_text())[-1]['clearance'],2)
        user_admin.change('Owner',{'action':'disable','user_id':'New'})
        self.assertEqual(len(json.loads(self.path.read_text())),1)

    def test_audit_failure_prevents_change(self):
        self.audit.side_effect=OSError('log unavailable')
        before=self.path.read_bytes()
        with self.assertRaises(OSError):user_admin.change('Owner',{'action':'disable','user_id':'Worker'})
        self.assertEqual(self.path.read_bytes(),before)

import http.client
import json
import threading
import unittest
from unittest.mock import patch
from http.server import HTTPServer
from src import web_server as web


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), web.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        web.Handler.attempts.clear()
        web.Handler.questions.clear()

    def request(self, path, data=None, origin=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = 'http://127.0.0.1:' + str(self.server.server_port)
        conn.request('GET' if data is None else 'POST', path, None if data is None else json.dumps(data), headers)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_static_and_traversal(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/../keys/token_key.txt')[0], 404)

    def test_origin_required(self):
        self.assertEqual(self.request('/api/login', {}, origin=False)[0], 403)

    def test_unauthenticated_question_never_opens_store(self):
        with patch.object(web, 'open_store') as store, patch.object(web, 'log_auth_failure'):
            self.assertEqual(self.request('/api/ask', {'question': 'secret'})[0], 401)
            store.assert_not_called()

    def test_login_cookie_and_audit_failure(self):
        user = {'user_id': 'demo', 'role': 'Engineer', 'department': 'Engineering'}
        with patch.object(web, 'load_users', return_value=({'demo': user}, [])), patch.object(web, 'check_credentials', return_value=True), patch.object(web, 'issue_token', return_value='signed'), patch.object(web, 'write_audit_entry') as audit:
            status, headers, _ = self.request('/api/login', {'user_id': 'demo', 'password': 'test'})
            self.assertEqual(status, 200)
            self.assertIn('HttpOnly', headers['Set-Cookie'])
            self.assertIn('SameSite=Strict', headers['Set-Cookie'])
            audit.side_effect = OSError()
            status, headers, _ = self.request('/api/login', {'user_id': 'demo', 'password': 'test'})
            self.assertEqual(status, 503)
            self.assertNotIn('Set-Cookie', headers)

    def test_answers_hide_status_and_reject_identity_override(self):
        with patch.object(web.Handler, 'user', return_value={'user_id': 'demo'}), patch.object(web, 'open_store') as store, patch.object(web, 'answer_question', return_value={'answer': 'Answer', 'sources': ['doc'], 'status': 'answered'}):
            self.assertEqual(self.request('/api/ask', {'question':'q', 'user_id':'CEO'})[0], 400)
            store.assert_not_called()
            status, _, body = self.request('/api/ask', {'question':'q'})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), {'answer':'Answer', 'sources':['doc']})
            store.return_value.close.assert_called_once()

    def test_rate_limit_and_logout(self):
        with patch.object(web, 'load_users', return_value=({}, [])), patch.object(web, 'log_auth_failure'):
            for _ in range(10):
                self.assertEqual(self.request('/api/login', {'user_id':'bad','password':'bad'})[0], 401)
            self.assertEqual(self.request('/api/login', {})[0], 429)
        self.assertIn('Max-Age=0', self.request('/api/logout', {})[1]['Set-Cookie'])

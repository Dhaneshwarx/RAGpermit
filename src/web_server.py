"""Loopback-only browser interface. Run: python -m src.web_server."""
import json
import os
import time
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from src.admin_access import is_admin
from src import document_admin
from src.config import workspace_path
from src.document_loader import load_document

from src.authentication import authenticate, AUTH_FAILED_MESSAGE
from src.authorization import load_users
from src.credentials import check_credentials
from src.issue_token import issue_token
from src.audit import write_audit_entry, log_auth_failure
from src.answering import answer_question, REFUSAL
from src.vector_store import open_store

ROOT = Path(__file__).resolve().parent.parent


class Handler(BaseHTTPRequestHandler):
    # One local process, serialized requests, bounded login and question attempts.
    attempts = deque()
    questions = deque()

    def log_message(self, *args):
        pass  # Never log passwords, tokens, or question bodies to the console.

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def reply(self, status, body, cookie=None, kind='application/json'):
        data = json.dumps(body).encode() if kind == 'application/json' else body
        self.send_response(status)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)

    def user(self):
        cookies = SimpleCookie()
        cookies.load(self.headers.get('Cookie', ''))
        token = cookies['permitrag'].value if 'permitrag' in cookies else None
        user_id, reason = authenticate(token)
        if reason:
            return None
        users, rejected = load_users()
        return users.get(user_id) if not rejected else None

    @staticmethod
    def limited(queue, maximum):
        now = time.monotonic()
        while queue and queue[0] <= now - 60:
            queue.popleft()
        if len(queue) >= maximum:
            return True
        queue.append(now)
        return False

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error': 'Request refused.'})
        if self.path == '/api/session':
            try:
                user = self.user()
                return self.reply(200 if user else 401, {'user': user, 'is_admin': bool(user and is_admin(user['user_id']))})
            except Exception:
                return self.reply(401, {'error': AUTH_FAILED_MESSAGE})
        if self.path == '/api/admin/documents':
            try:
                user = self.user()
                if not user or not is_admin(user['user_id']):
                    return self.reply(403, {'error': 'Administrator access required.'})
                write_audit_entry({'status': 'admin_documents_listed', 'user_id': user['user_id']})
                return self.reply(200, document_admin.inventory())
            except Exception:
                return self.reply(503, {'error': 'Unable to load documents.'})
        assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if self.path not in assets:
            return self.reply(404, {'error': 'Not found.'})
        name, kind = assets[self.path]
        self.reply(200, (ROOT / 'web' / name).read_bytes(), kind=kind)

    def do_POST(self):
        origin = 'http://127.0.0.1:' + str(self.server.server_port)
        if not self.valid_host() or self.headers.get('Origin') != origin or self.headers.get('Content-Type') != 'application/json':
            return self.reply(403, {'error': 'Request refused.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1250000:
                return self.reply(400, {'error': 'Invalid request.'})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, OSError):
            return self.reply(400, {'error': 'Invalid request.'})
        try:
            if self.path == '/api/login':
                if self.limited(self.attempts, 10):
                    return self.reply(429, {'error': 'Too many attempts. Try again in a minute.'})
                uid, password = data.get('user_id'), data.get('password')
                users, rejected = load_users()
                if set(data) != {'user_id', 'password'} or not isinstance(uid, str) or not isinstance(password, str) or len(password) > 128 or rejected or uid not in users or not check_credentials(uid, password):
                    log_auth_failure('password_login_failed')
                    return self.reply(401, {'error': AUTH_FAILED_MESSAGE})
                token = issue_token(uid)
                write_audit_entry({'status': 'login_success', 'user_id': uid})
                return self.reply(200, {'user': users[uid], 'is_admin': is_admin(uid)}, 'permitrag=' + token + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=900')
            if self.path == '/api/logout':
                return self.reply(200, {'ok': True}, 'permitrag=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if self.path == '/api/admin/documents':
                user = self.user()
                if not user or not is_admin(user['user_id']):
                    return self.reply(403, {'error': 'Administrator access required.'})
                try:
                    if data.get('action') == 'reindex':
                        count = document_admin.reindex(user['user_id'])
                        return self.reply(200, {'chunks': count})
                    document_admin.change(user['user_id'], data.get('action'), data.get('doc_id'), data.get('content'))
                    return self.reply(200, {'ok': True, 'needs_indexing': True})
                except ValueError as error:
                    return self.reply(400, {'error': str(error)})
            if self.path != '/api/ask':
                return self.reply(404, {'error': 'Not found.'})
            user = self.user()
            if not user:
                log_auth_failure('web_session_invalid')
                return self.reply(401, {'error': AUTH_FAILED_MESSAGE})
            question = data.get('question')
            if set(data) != {'question'} or not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
                return self.reply(400, {'error': 'Enter a question of 1-2000 characters.'})
            if self.limited(self.questions, 20):
                return self.reply(429, {'error': 'Too many questions. Try again in a minute.'})
            if document_admin.dirty():
                return self.reply(503, {'error': 'Documents are being updated. Please try again after indexing.'})
            client = open_store()
            try:
                result = answer_question(client, user, question, user_id=user['user_id'])
            finally:
                client.close()
            self.reply(200, {'answer': result['answer'], 'sources': result['sources']})
        except Exception:
            try:
                write_audit_entry({'status': 'error', 'channel': 'web'})
            except Exception:
                pass
            self.reply(503, {'error': REFUSAL if self.path == '/api/ask' else 'Unable to complete the operation. Please try again.'})


def main():
    os.chdir(ROOT)
    server = HTTPServer(('127.0.0.1', 8000), Handler)
    print('PermitRAG is running at http://127.0.0.1:8000 (Ctrl+C to stop)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

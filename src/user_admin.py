"""Trusted administrator user operations. No public registration."""
import json
import os
from src.config import workspace_path
from src.authorization import load_users,validate_user
from src.credentials import credential_path
from src.passwords import hash_password
from src.audit import write_audit_entry
from src.admin_access import is_admin
from src.revocation import revoke_user


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.pending')
    with temporary.open('w',encoding='utf-8') as file:
        json.dump(value,file,indent=2)
    os.replace(temporary,path)


def inventory():
    users,rejected=load_users()
    if rejected:raise ValueError('Fix invalid user records first.')
    return {'users':list(users.values())}


def change(actor,data):
    if not is_admin(actor):raise PermissionError('Administrator access required.')
    users,rejected=load_users()
    if rejected:raise ValueError('Fix invalid user records first.')
    action=data.get('action');uid=data.get('user_id')
    if not isinstance(uid,str) or not uid.strip() or len(uid)>256:raise ValueError('Enter a valid user ID.')
    if action not in ('create','update','reset','disable','revoke'):raise ValueError('Unknown account operation.')
    if action=='create' and uid in users:raise ValueError('User already exists.')
    if action!='create' and uid not in users:raise ValueError('User not found.')
    if action in ('disable','update') and is_admin(uid):raise ValueError('Administrator accounts cannot be disabled or changed here.')
    record=None;password_record=None
    if action in ('create','update'):
        record=validate_user({key:data.get(key) for key in ('user_id','department','role','clearance')})
    if action in ('create','reset'):
        password_record={'user_id':uid,'password':hash_password(data.get('password'))}
    write_audit_entry({'status':'admin_user_change','user_id':actor,'target_user':uid,'action':action})
    # Revoke before mutation, including reused account IDs.
    revoke_user(uid)
    if password_record:atomic(credential_path(uid),password_record)
    if action=='disable':del users[uid]
    if record:users[uid]=record
    if action in ('create','update','disable'):atomic(workspace_path('data/users.json'),list(users.values()))

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .storage import transaction

bearer = HTTPBearer(auto_error=False)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 310_000)
    return f'{salt}${digest.hex()}'


def issue_token(user):
    return jwt.encode({'sub': str(user['id']), 'exp': datetime.now(timezone.utc) + timedelta(hours=8)},
                      os.environ['JWT_SECRET'], algorithm='HS256')


def authenticate(creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
    auth_error = HTTPException(401, '登录已失效，请重新登录', headers={'WWW-Authenticate': 'Bearer'})
    if not creds:
        raise auth_error
    try:
        subject = jwt.decode(creds.credentials, os.environ['JWT_SECRET'], algorithms=['HS256'],
                             options={'require': ['sub', 'exp']})['sub']
        user_id = int(subject)
    except (jwt.InvalidTokenError, ValueError):
        raise auth_error from None
    with transaction() as cur:
        cur.execute('SELECT id, username, role FROM users WHERE id=%s', (user_id,))
        user = cur.fetchone()
    if not user:
        raise auth_error
    return user


def permit(role):
    def authorized(user=Depends(authenticate)):
        if user['role'] != role:
            raise HTTPException(403, '当前岗位无权执行此操作')
        return user
    return authorized


def login(username, password, cur):
    cur.execute('SELECT id, username, role, password_hash FROM users WHERE username=%s', (username,))
    user = cur.fetchone()
    stored = user.pop('password_hash') if user else '00000000000000000000000000000000$invalid'
    candidate = password_hash(password, stored.split('$', 1)[0])
    if not (hmac.compare_digest(candidate, stored) and user):
        raise HTTPException(401, '账号或口令不正确')
    return {'token': issue_token(user), 'user': user}

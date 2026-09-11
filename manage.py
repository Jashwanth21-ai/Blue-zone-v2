"""Explicit, local administration; no public administrator bootstrap endpoint."""
import argparse
import getpass
import sqlite3
import time
from .db import initialize,connect,audit
from .curriculum import seed
from .models import Register
from .security import hasher

parser=argparse.ArgumentParser(description='BlueZone local administration')
parser.add_argument('action',choices=['create-admin','reset-password'])
parser.add_argument('--email',required=True)
parser.add_argument('--name',default='Administrator')
args=parser.parse_args()
password=getpass.getpass('New password (12–128 characters): ')
if password!=getpass.getpass('Confirm password: '): raise SystemExit('Passwords do not match')
validated=Register(email=args.email,name=args.name,password=password)
initialize(); seed()
with connect() as db:
    if args.action=='create-admin':
        try:
            cur=db.execute("INSERT INTO users(email,name,password,role,created) VALUES(?,?,?,'admin',?)",(validated.email,validated.name,hasher.hash(password),int(time.time())))
        except sqlite3.IntegrityError: raise SystemExit('Account already exists. No changes made.')
        audit(db,cur.lastrowid,'cli.admin_created',cur.lastrowid)
    else:
        user=db.execute('SELECT id FROM users WHERE email=?',(validated.email,)).fetchone()
        if not user: raise SystemExit('Account not found')
        db.execute('UPDATE users SET password=? WHERE id=?',(hasher.hash(password),user['id']))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        audit(db,user['id'],'cli.password_reset',user['id'])
print('Done.')

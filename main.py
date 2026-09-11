import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .db import ROOT, initialize, connect, audit
from .security import digest, hasher, verify, DUMMY_HASH, rate_limit, answer_digest
from .models import Credentials, Register, PasswordChange, Submission, Command, TutorMessage, UserUpdate, UnitWrite, PathWrite
from .learning import catalog, accessible_unit, public_content, submit
from .curriculum import seed
from . import tutor

COOKIE='bluezone_session'

def create_app():
    production=os.environ.get('BLUEZONE_ENV')=='production'
    origin=os.environ.get('BLUEZONE_ORIGIN','http://127.0.0.1:8000').rstrip('/')
    if production and not origin.startswith('https://'):
        raise RuntimeError('Production requires BLUEZONE_ORIGIN with HTTPS')
    allowed_origins={origin} if production else {origin,'http://localhost:8000','http://127.0.0.1:8000'}

    @asynccontextmanager
    async def lifespan(app):
        initialize()
        seed()
        yield

    app=FastAPI(title='BlueZone API',version='1.0.0',lifespan=lifespan,docs_url=None,redoc_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=[urlparse(origin).hostname] if production else list({urlparse(origin).hostname,'127.0.0.1','localhost','testserver'}))

    @app.middleware('http')
    async def boundary(request:Request,call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            if request.headers.get('origin') not in allowed_origins:
                return JSONResponse({'detail':'Request origin is not allowed'},403)
            body=bytearray()
            async for part in request.stream():
                body.extend(part)
                if len(body)>100000:
                    return JSONResponse({'detail':'Request too large'},413)
            request._body=bytes(body)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        if production: response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    def current(request:Request):
        token=request.cookies.get(COOKIE,'')
        with connect() as db:
            row=db.execute('SELECT u.*,s.csrf,s.token FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(digest(token),int(time.time()))).fetchone()
        if not row: raise HTTPException(401,'Please sign in to continue.')
        user=dict(row)
        if request.method in ('POST','PUT','PATCH','DELETE') and not secrets.compare_digest(request.headers.get('x-csrf-token',''),user['csrf']):
            raise HTTPException(403,'Session verification failed. Refresh and try again.')
        return user

    def admin(user=Depends(current)):
        if user['role']!='admin': raise HTTPException(403,'Administrator access required.')
        return user

    def public_user(user):
        return {k:user[k] for k in ('id','email','name','role')}

    def session(db,user_id,response,request):
        now=int(time.time())
        token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<=? OR token=?',(now,digest(request.cookies.get(COOKIE,''))))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),user_id,csrf,now+43200))
        response.set_cookie(COOKIE,token,httponly=True,secure=production,samesite='strict',max_age=43200,path='/')
        return csrf

    @app.get('/api/health')
    def health():
        with connect() as db: db.execute('SELECT 1').fetchone()
        return {'status':'ok','version':'1.0.0'}

    @app.post('/api/auth/register',status_code=201)
    def register(payload:Register,request:Request,response:Response):
        rate_limit('register:'+request.client.host,10,3600)
        hashed=hasher.hash(payload.password)
        try:
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT count(*) FROM users').fetchone()[0]>=int(os.environ.get('BLUEZONE_MAX_USERS','100')):
                    raise HTTPException(409,'This learning cohort is full. Contact your administrator.')
                cur=db.execute('INSERT INTO users(email,name,password,created) VALUES(?,?,?,?)',(payload.email,payload.name,hashed,int(time.time())))
                csrf=session(db,cur.lastrowid,response,request)
                user=db.execute('SELECT * FROM users WHERE id=?',(cur.lastrowid,)).fetchone()
                audit(db,user['id'],'account.register',user['id'])
                return {'user':public_user(user),'csrf':csrf}
        except sqlite3.IntegrityError:
            raise HTTPException(409,'An account with this email already exists. Sign in instead.')

    @app.post('/api/auth/login')
    def login(payload:Credentials,request:Request,response:Response):
        rate_limit('login-ip:'+request.client.host,30,900)
        rate_limit('login-account:'+digest(payload.email),10,900)
        with connect() as db:
            user=db.execute('SELECT * FROM users WHERE email=?',(payload.email,)).fetchone()
            ok=verify(payload.password,user['password'] if user else DUMMY_HASH)
            if not ok or not user or not user['active']: raise HTTPException(401,'Email or password is incorrect, or the account is unavailable.')
            csrf=session(db,user['id'],response,request)
            audit(db,user['id'],'account.login',user['id'])
            return {'user':public_user(user),'csrf':csrf}

    @app.get('/api/auth/me')
    def me(user=Depends(current)):
        return {'user':public_user(user),'csrf':user['csrf'],'tutor_configured':tutor.configured()}

    @app.post('/api/auth/logout')
    def logout(response:Response,user=Depends(current)):
        with connect() as db: db.execute('DELETE FROM sessions WHERE token=?',(user['token'],))
        response.delete_cookie(COOKIE,path='/')
        return {'ok':True}

    @app.post('/api/auth/password')
    def password(payload:PasswordChange,response:Response,user=Depends(current)):
        rate_limit('password:'+str(user['id']),5,900)
        if not verify(payload.current_password,user['password']): raise HTTPException(400,'Current password is incorrect.')
        hashed=hasher.hash(payload.new_password)
        with connect() as db:
            db.execute('UPDATE users SET password=? WHERE id=?',(hashed,user['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
            audit(db,user['id'],'account.password_changed',user['id'])
        response.delete_cookie(COOKIE,path='/')
        return {'ok':True}

    @app.get('/api/catalog')
    def get_catalog(user=Depends(current)):
        with connect() as db:
            return {'paths':[dict(r) for r in db.execute('SELECT * FROM paths ORDER BY position')], 'units':catalog(db,user['id'])}

    @app.get('/api/units/{unit_id}')
    def detail(unit_id:str,user=Depends(current)):
        with connect() as db:
            meta,content=accessible_unit(db,user['id'],unit_id)
            return {**meta,'content':public_content(content)}

    @app.post('/api/units/{unit_id}/command')
    def command(unit_id:str,payload:Command,user=Depends(current)):
        rate_limit('command:'+str(user['id']),120,60)
        with connect() as db:
            _,content=accessible_unit(db,user['id'],unit_id)
        cmd=' '.join(payload.command.strip().split())
        if cmd=='help': return {'output':'Available simulated commands:\n'+'\n'.join(content['commands'])+'\nhelp'}
        if cmd not in content['commands']: raise HTTPException(400,'That command is not part of this simulation. Type help for available commands.')
        return {'output':content['commands'][cmd]}

    @app.post('/api/units/{unit_id}/submit')
    def assess(unit_id:str,payload:Submission,user=Depends(current)):
        rate_limit('submit:'+str(user['id']),30,60)
        with connect() as db: return submit(db,user['id'],unit_id,payload.answers)

    @app.get('/api/progress')
    def progress(user=Depends(current)):
        with connect() as db:
            units=catalog(db,user['id'])
            completed=[u for u in units if u['completed']]
            xp=db.execute('SELECT COALESCE(sum(xp),0) FROM completions WHERE user_id=?',(user['id'],)).fetchone()[0]
            activities=[dict(r) for r in db.execute('SELECT c.completed,c.xp,u.title,u.kind FROM completions c JOIN units u ON u.id=c.unit_id WHERE user_id=? ORDER BY c.completed DESC LIMIT 20',(user['id'],))]
            attempts=db.execute('SELECT count(*) FROM attempts WHERE user_id=?',(user['id'],)).fetchone()[0]
            badges=[]
            if completed: badges.append({'title':'First signal','description':'Passed your first mission.'})
            for p in db.execute('SELECT * FROM paths ORDER BY position'):
                path_units=[u for u in units if u['path_id']==p['id']]
                if path_units and all(u['completed'] for u in path_units): badges.append({'title':p['title'],'description':'Completed every mission in this path.'})
            if any(u['id']=='final-mission' for u in completed): badges.append({'title':'Blue Horizon','description':'Completed the advanced incident capstone.'})
            return {'xp':xp,'completed':len(completed),'total':len(units),'attempts':attempts,'activities':activities,'badges':badges,'next':next((u for u in units if not u['locked'] and not u['completed']),None)}

    @app.get('/api/tutor/{unit_id}')
    def history(unit_id:str,user=Depends(current)):
        with connect() as db:
            accessible_unit(db,user['id'],unit_id)
            rows=db.execute('SELECT role,message,mode,created FROM chats WHERE user_id=? AND unit_id=? ORDER BY id DESC LIMIT 40',(user['id'],unit_id)).fetchall()
            return {'messages':[dict(r) for r in reversed(rows)],'configured':tutor.configured()}

    @app.post('/api/tutor')
    def chat(payload:TutorMessage,user=Depends(current)):
        rate_limit('tutor-minute:'+str(user['id']),8,60)
        rate_limit('tutor-day:'+str(user['id']),100,86400)
        with connect() as db:
            _,content=accessible_unit(db,user['id'],payload.unit_id)
            rows=db.execute('SELECT role,message FROM chats WHERE user_id=? AND unit_id=? ORDER BY id DESC LIMIT 10',(user['id'],payload.unit_id)).fetchall()
        answer,mode=tutor.respond(content,payload.message,[{'role':r['role'],'content':r['message']} for r in reversed(rows)],payload.allow_external)
        with connect() as db:
            for role,message in [('user',payload.message),('assistant',answer)]:
                db.execute('INSERT INTO chats(user_id,unit_id,role,message,mode,created) VALUES(?,?,?,?,?,?)',(user['id'],payload.unit_id,role,message,mode,int(time.time())))
            db.execute('DELETE FROM chats WHERE user_id=? AND unit_id=? AND id NOT IN (SELECT id FROM chats WHERE user_id=? AND unit_id=? ORDER BY id DESC LIMIT 40)',(user['id'],payload.unit_id,user['id'],payload.unit_id))
        return {'message':answer,'mode':mode}

    @app.delete('/api/tutor/{unit_id}')
    def clear_history(unit_id:str,user=Depends(current)):
        with connect() as db: db.execute('DELETE FROM chats WHERE user_id=? AND unit_id=?',(user['id'],unit_id))
        return {'ok':True}

    @app.get('/api/admin/overview')
    def overview(user=Depends(admin)):
        with connect() as db:
            return {'users':[dict(r) for r in db.execute('SELECT u.id,u.email,u.name,u.role,u.active,u.created, (SELECT count(*) FROM completions c WHERE c.user_id=u.id) AS completed FROM users u ORDER BY u.id')],
              'audit':[dict(r) for r in db.execute('SELECT a.*,u.name FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 100')],
              'units':[{**dict(r),'content':json.loads(r['content'])} for r in db.execute('SELECT * FROM units ORDER BY position')],
              'paths':[dict(r) for r in db.execute('SELECT * FROM paths ORDER BY position')]}

    @app.patch('/api/admin/users/{user_id}')
    def update_user(user_id:int,payload:UserUpdate,user=Depends(admin)):
        if user_id==user['id']: raise HTTPException(400,'Use another administrator to change your own role or account status.')
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone(): raise HTTPException(404,'User not found')
            db.execute('UPDATE users SET role=?,active=? WHERE id=?',(payload.role,int(payload.active),user_id))
            db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
            audit(db,user['id'],'admin.user_updated',user_id)
        return {'ok':True}

    @app.put('/api/admin/paths/{path_id}')
    def save_path(path_id:str,payload:PathWrite,user=Depends(admin)):
        if path_id!=payload.id: raise HTTPException(422,'Path ID mismatch')
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM paths WHERE id=?',(path_id,)).fetchone()
            if old: db.execute('UPDATE paths SET title=?,description=?,level=? WHERE id=?',(payload.title,payload.description,payload.level,path_id))
            else:
                position=db.execute('SELECT COALESCE(max(position),0)+1 FROM paths').fetchone()[0]
                db.execute('INSERT INTO paths VALUES(?,?,?,?,?)',(path_id,payload.title,payload.description,payload.level,position))
            audit(db,user['id'],'admin.path_saved',path_id)
        return {'ok':True}

    @app.put('/api/admin/units/{unit_id}')
    def save_unit(unit_id:str,payload:UnitWrite,user=Depends(admin)):
        if unit_id!=payload.id: raise HTTPException(422,'Mission ID mismatch')
        content=payload.content.model_dump()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM paths WHERE id=?',(payload.path_id,)).fetchone(): raise HTTPException(422,'Unknown learning path')
            old=db.execute('SELECT * FROM units WHERE id=?',(unit_id,)).fetchone()
            if (old and old['revision']!=payload.revision) or (not old and payload.revision!=0): raise HTTPException(409,'This mission changed. Reload the editor before saving.')
            old_tasks=json.loads(old['content'])['tasks'] if old else []
            for i,t in enumerate(content['tasks']):
                answer=t.pop('answer',None)
                if answer:
                    if t['options'] and answer not in t['options']: raise HTTPException(422,'Correct answer must match an option')
                    t['answer_hash']=answer_digest(answer)
                elif not (i<len(old_tasks) and t['answer_hash']==old_tasks[i]['answer_hash']):
                    raise HTTPException(422,'Provide a correct answer for every new or changed assessment.')
                if t['options'] and not any(answer_digest(option)==t['answer_hash'] for option in t['options']):
                    raise HTTPException(422,'At least one option must match the correct answer.')
            position=old['position'] if old else db.execute('SELECT COALESCE(max(position),0)+1 FROM units').fetchone()[0]
            revision=(old['revision']+1) if old else 1
            db.execute('INSERT INTO units(id,path_id,title,summary,kind,minutes,xp,position,published,content,revision) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET path_id=excluded.path_id,title=excluded.title,summary=excluded.summary,kind=excluded.kind,minutes=excluded.minutes,xp=excluded.xp,published=excluded.published,content=excluded.content,revision=excluded.revision',
              (unit_id,payload.path_id,payload.title,payload.summary,payload.kind,payload.minutes,payload.xp,position,int(payload.published),json.dumps(content),revision))
            audit(db,user['id'],'admin.mission_saved',unit_id)
        return {'ok':True,'revision':revision}

    app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
    @app.get('/')
    def index(): return FileResponse(ROOT/'app/static/landing.html')
    @app.get('/app')
    def workspace(): return FileResponse(ROOT/'app/static/index.html')
    return app

app=create_app()

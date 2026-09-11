import json
import time
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app, COOKIE
from app.db import connect, initialize
from app.curriculum import UNITS
from app.security import hasher,digest,rate_limit
from app import tutor

ORIGIN={'Origin':'http://127.0.0.1:8000'}
PASSWORD='Correct-horse-blue-zone!'

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('BLUEZONE_DB',str(tmp_path/'test.db'))
    monkeypatch.delenv('BLUEZONE_ENV',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('OPENAI_MODEL',raising=False)
    with TestClient(create_app(),headers=ORIGIN) as c: yield c

def register(c,email='learner@example.com'):
    r=c.post('/api/auth/register',json={'name':'Test Learner','email':email,'password':PASSWORD})
    assert r.status_code==201,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf']
    return r.json()['user']

def login(c,email='learner@example.com',password=PASSWORD):
    r=c.post('/api/auth/login',json={'email':email,'password':password})
    assert r.status_code==200,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf']
    return r

def promote(user_id):
    with connect() as db: db.execute("UPDATE users SET role='admin' WHERE id=?",(user_id,))

def solve(c,u):
    return c.post('/api/units/'+u['id']+'/submit',json={'answers':[t['answer'] for t in u['content']['tasks']]})

def test_registration_password_storage_and_boundaries(client):
    u=register(client)
    with connect() as db:
        row=db.execute('SELECT * FROM users').fetchone()
        assert row['password'].startswith('$argon2id$') and row['password']!=PASSWORD
        session=db.execute('SELECT * FROM sessions').fetchone()
        assert session['token']==digest(client.cookies.get(COOKIE))
    cookie=client.get('/api/auth/me')
    assert cookie.status_code==200
    assert 'password' not in cookie.text
    assert client.get('/api/admin/overview').status_code==403
    assert client.post('/api/auth/logout',headers={'X-CSRF-Token':'wrong'},json={}).status_code==403
    assert client.post('/api/auth/logout',headers={'Origin':'https://evil.example'},json={}).status_code==403
    assert client.post('/api/auth/logout',json={}).status_code==200
    assert client.get('/api/auth/me').status_code==401

def test_validation_duplicate_case_and_cookie(client):
    r=client.post('/api/auth/register',json={'name':'A','email':'not-email','password':'short'})
    assert r.status_code==422
    r=client.post('/api/auth/register',json={'name':'A','email':'A@example.com','password':PASSWORD})
    assert r.status_code==201
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
    r=client.post('/api/auth/register',json={'name':'A','email':'a@EXAMPLE.com','password':PASSWORD})
    assert r.status_code==409

def test_entire_learning_journey_and_persistence(client):
    register(client)
    catalog=client.get('/api/catalog').json()
    assert len(catalog['paths'])==3 and len(catalog['units'])==12
    assert not catalog['units'][0]['locked'] and catalog['units'][1]['locked']
    assert client.get('/api/units/final-mission').status_code==403
    assert solve(client,UNITS[-1]).status_code==403
    for u in UNITS:
        # Simulate the time spent reading each mission without weakening runtime limits.
        with connect() as db: db.execute("DELETE FROM limits WHERE key LIKE 'submit:%'")
        detail=client.get('/api/units/'+u['id'])
        assert detail.status_code==200,detail.text
        assert 'answer_hash' not in detail.text and '"answer"' not in detail.text
        for cmd,output in u['content']['commands'].items():
            assert client.post('/api/units/'+u['id']+'/command',json={'command':cmd}).json()['output']==output
        wrong=client.post('/api/units/'+u['id']+'/submit',json={'answers':['incorrect']*len(u['content']['tasks'])})
        assert wrong.status_code==200 and not wrong.json()['passed']
        result=solve(client,u)
        assert result.status_code==200 and result.json()['passed'],result.text
        assert result.json()['xp_awarded']==u['xp']
        assert solve(client,u).json()['xp_awarded']==0
    p=client.get('/api/progress').json()
    assert p['completed']==12 and p['xp']==sum(u['xp'] for u in UNITS)
    assert p['next'] is None and any(b['title']=='Blue Horizon' for b in p['badges'])
    client.post('/api/auth/logout',json={});login(client)
    assert client.get('/api/progress').json()['completed']==12
    initialize()
    assert client.get('/api/progress').json()['xp']==p['xp']

def test_expiry_and_password_change_revoke_all_sessions(client):
    user=register(client)
    old_token=client.cookies.get(COOKIE)
    client.cookies.clear();login(client)
    new_token=client.cookies.get(COOKIE)
    assert new_token!=old_token
    r=client.post('/api/auth/password',json={'current_password':PASSWORD,'new_password':'A-new-secure-passphrase'})
    assert r.status_code==200
    with connect() as db: assert db.execute('SELECT count(*) FROM sessions WHERE user_id=?',(user['id'],)).fetchone()[0]==0
    assert client.get('/api/auth/me').status_code==401
    login(client,password='A-new-secure-passphrase')
    with connect() as db: db.execute('UPDATE sessions SET expires=?',(int(time.time())-1,))
    assert client.get('/api/auth/me').status_code==401

def test_cross_account_progress_and_chat_isolation(client):
    register(client)
    solve(client,UNITS[0])
    r=client.post('/api/tutor',json={'unit_id':UNITS[0]['id'],'message':'give me a hint'})
    assert r.status_code==200 and r.json()['mode']=='guide'
    assert len(client.get('/api/tutor/network-basics').json()['messages'])==2
    client.post('/api/auth/logout',json={})
    register(client,'second@example.com')
    assert client.get('/api/progress').json()['completed']==0
    assert client.get('/api/tutor/network-basics').json()['messages']==[]
    assert client.post('/api/tutor',json={'unit_id':'final-mission','message':'hint'}).status_code==403
    assert client.get('/api/admin/overview').status_code==403

def test_simulated_terminal_never_executes(client):
    register(client);solve(client,UNITS[0])
    for cmd in ['whoami; dir','cat ../../secret','python -c print(1)','curl https://example.com']:
        assert client.post('/api/units/linux-permissions/command',json={'command':cmd}).status_code==400
    assert 'ls -l' in client.post('/api/units/linux-permissions/command',json={'command':'help'}).json()['output']

def test_admin_cohort_suspend_and_role_revoke(client):
    admin=register(client,'admin@example.com');promote(admin['id'])
    client.post('/api/auth/logout',json={})
    learner=register(client)
    token=client.cookies.get(COOKIE)
    client.cookies.clear();login(client,'admin@example.com')
    assert client.get('/api/admin/overview').status_code==200
    assert client.patch('/api/admin/users/'+str(admin['id']),json={'role':'learner','active':False}).status_code==400
    assert client.patch('/api/admin/users/'+str(learner['id']),json={'role':'learner','active':False}).status_code==200
    with connect() as db:
        assert not db.execute('SELECT * FROM sessions WHERE token=?',(digest(token),)).fetchone()
        assert db.execute('SELECT action FROM audit ORDER BY id DESC').fetchone()[0]=='admin.user_updated'
    client.cookies.clear()
    assert client.post('/api/auth/login',json={'email':'learner@example.com','password':PASSWORD}).status_code==401

def test_admin_content_crud_revision_and_no_answer_leak(client):
    u=register(client);promote(u['id'])
    data=client.get('/api/admin/overview').json()
    mission=data['units'][0]
    mission['title']='Updated title'
    assert client.put('/api/admin/units/'+mission['id'],json=mission).status_code==200
    assert client.put('/api/admin/units/'+mission['id'],json=mission).status_code==409
    detail=client.get('/api/units/'+mission['id'])
    assert detail.json()['title']=='Updated title' and 'answer_hash' not in detail.text
    path={'id':'new-path','title':'New path','description':'A focused addition','level':'Advanced'}
    assert client.put('/api/admin/paths/new-path',json=path).status_code==200
    new={**mission,'id':'new-mission','path_id':'new-path','revision':0,'published':False}
    new['content']['tasks']=[{'prompt':'Test question','hint':'Test hint','answer':'yes','options':['yes','no']}]
    assert client.put('/api/admin/units/new-mission',json=new).status_code==200
    assert client.get('/api/units/new-mission').status_code==404
    assert not any(x['id']=='new-mission' for x in client.get('/api/catalog').json()['units'])
    new['revision']=1;new['published']=True
    assert client.put('/api/admin/units/new-mission',json=new).status_code==200
    assert client.get('/api/units/new-mission').status_code==403

def test_tutor_adapter_contract_fallback_and_consent(monkeypatch):
    c=UNITS[0]['content']
    monkeypatch.setenv('OPENAI_API_KEY','test-only');monkeypatch.setenv('OPENAI_MODEL','configured-model')
    class FakeClient:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):
            assert url=='https://api.openai.com/v1/responses'
            assert json['store'] is False
            assert 'answer_hash' not in str(json)
            return httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':'Consider the trust boundary.'}]}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(tutor.httpx,'Client',FakeClient)
    assert tutor.respond(c,'Explain',[],False)[1]=='guide'
    assert tutor.respond(c,'Explain',[],True)==('Consider the trust boundary.','ai')
    def fail(*args,**kwargs):raise httpx.ConnectError('offline')
    monkeypatch.setattr(FakeClient,'post',fail)
    assert tutor.respond(c,'Explain',[],True)[1]=='fallback'

def test_rate_limit_and_payload_limits(client):
    for _ in range(3): rate_limit('test-key',3,60)
    with pytest.raises(Exception) as err: rate_limit('test-key',3,60)
    assert err.value.status_code==429
    assert client.post('/api/auth/login',content='x'*100001).status_code==413
    assert client.get('/api/health').json()['status']=='ok'
    assert client.get('/').headers['x-content-type-options']=='nosniff'

def test_concurrent_completion_awards_once(client):
    register(client)
    def attempt(_):return solve(client,UNITS[0]).json()['xp_awarded']
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(attempt,range(4)))
    assert sum(results)==UNITS[0]['xp']
    assert client.get('/api/progress').json()['completed']==1

def test_production_https_required(monkeypatch):
    monkeypatch.setenv('BLUEZONE_ENV','production');monkeypatch.setenv('BLUEZONE_ORIGIN','http://example.com')
    with pytest.raises(RuntimeError): create_app()


def test_cohort_capacity_and_signup_role_cannot_be_injected(client,monkeypatch):
    monkeypatch.setenv('BLUEZONE_MAX_USERS','1')
    r=client.post('/api/auth/register',json={'name':'Learner','email':'one@example.com','password':PASSWORD,'role':'admin'})
    assert r.status_code==201 and r.json()['user']['role']=='learner'
    r=client.post('/api/auth/register',json={'name':'Learner','email':'two@example.com','password':PASSWORD})
    assert r.status_code==409

def test_production_cookie_host_origin_and_https(client,monkeypatch):
    monkeypatch.setenv('BLUEZONE_ENV','production')
    monkeypatch.setenv('BLUEZONE_ORIGIN','https://training.example.com')
    with TestClient(create_app(),base_url='https://training.example.com',headers={'Origin':'https://training.example.com'}) as c:
        r=c.post('/api/auth/register',json={'name':'Production fixture','email':'prod@example.com','password':PASSWORD})
        assert r.status_code==201 and 'Secure' in r.headers['set-cookie']
        assert r.headers['strict-transport-security']=='max-age=31536000'
        assert c.get('/api/health',headers={'Host':'attacker.example'}).status_code==400
        assert c.post('/api/auth/logout',headers={'Origin':'https://attacker.example'},json={}).status_code==403

def test_login_throttling(client):
    register(client)
    client.post('/api/auth/logout',json={})
    for _ in range(10):
        assert client.post('/api/auth/login',json={'email':'learner@example.com','password':'incorrect-long-password'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'learner@example.com','password':PASSWORD}).status_code==429

def test_one_hundred_independent_learner_sessions(client):
    # A functional concurrency check, not a production throughput benchmark.
    now=int(time.time())
    shared_hash=hasher.hash(PASSWORD)
    with connect() as db:
        for i in range(100):
            cur=db.execute('INSERT INTO users(email,name,password,created) VALUES(?,?,?,?)',(f'cohort{i}@example.test',f'Learner {i}',shared_hash,now))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(f'fixture-token-{i}'),cur.lastrowid,'fixture-csrf',now+3600))
    def read(i):
        r=client.get('/api/progress',headers={'Cookie':f'{COOKIE}=fixture-token-{i}'})
        return r.status_code,r.json()['completed'],r.json()['total']
    with ThreadPoolExecutor(max_workers=10) as pool: results=list(pool.map(read,range(100)))
    assert results==[(200,0,12)]*100

def test_no_reflected_html_or_public_answer_source(client):
    register(client)
    assert client.get('/static/../curriculum.py').status_code==404
    assert client.get('/app/curriculum.py').status_code==404
    assert client.get('/data/bluezone.db').status_code==404
    assert "script-src 'self'" in client.get('/').headers['content-security-policy']
    assert client.get('/api/progress').headers['cache-control']=='no-store'

def test_configured_lan_host_accepts_login_but_not_other_origins(client,monkeypatch):
    monkeypatch.setenv('BLUEZONE_ORIGIN','http://192.168.1.5:8001')
    with TestClient(create_app(),base_url='http://192.168.1.5:8001',headers={'Origin':'http://192.168.1.5:8001'}) as c:
        r=c.post('/api/auth/register',json={'name':'LAN Learner','email':'lan@example.test','password':PASSWORD})
        assert r.status_code==201
        c.headers['X-CSRF-Token']=r.json()['csrf']
        assert c.get('/api/catalog').status_code==200
        assert c.post('/api/auth/logout',headers={'Origin':'http://192.168.1.99:8001'},json={}).status_code==403
        assert c.get('/api/health',headers={'Host':'192.168.1.99:8001'}).status_code==400
        assert c.post('/api/auth/logout',json={}).status_code==200

def test_public_landing_and_protected_workspace(client):
    page=client.get('/')
    assert page.status_code==200 and 'The confidence' in page.text
    assert '/app?mode=register' in page.text
    assert client.get('/app').status_code==200
    assert client.get('/static/landing.css').status_code==200
    assert client.get('/static/landing.js').status_code==200
    assert client.get('/api/catalog').status_code==401

def test_production_does_not_accept_an_extra_proxy_host(client,monkeypatch):
    monkeypatch.setenv('BLUEZONE_ENV','production')
    monkeypatch.setenv('BLUEZONE_ORIGIN','https://training.example.com')
    monkeypatch.setenv('BLUEZONE_TRUSTED_HOSTS','another.example.com')
    with TestClient(create_app(),base_url='https://training.example.com') as c:
        assert c.get('/api/health').status_code==200
        assert c.get('/api/health',headers={'Host':'another.example.com'}).status_code==400

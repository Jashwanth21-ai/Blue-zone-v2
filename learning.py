"""Learning service; only this boundary decides unlocks and awards."""
import json
import secrets
import time
from fastapi import HTTPException
from .security import answer_digest

def catalog(db, user_id):
    done={r['unit_id']:r['completed'] for r in db.execute('SELECT * FROM completions WHERE user_id=?',(user_id,))}
    rows=db.execute('SELECT id,path_id,title,summary,kind,minutes,xp,position,published,revision FROM units WHERE published=1 ORDER BY position').fetchall()
    items=[]
    unlocked=True
    for row in rows:
        u=dict(row)
        u['completed']=u['id'] in done
        u['completed_at']=done.get(u['id'])
        u['locked']=not unlocked and not u['completed']
        items.append(u)
        if not u['completed']: unlocked=False
    return items

def accessible_unit(db,user_id,unit_id):
    meta=next((u for u in catalog(db,user_id) if u['id']==unit_id),None)
    if not meta: raise HTTPException(404,'Mission not found')
    if meta['locked']: raise HTTPException(403,'Complete the earlier missions to unlock this mission.')
    row=db.execute('SELECT content FROM units WHERE id=?',(unit_id,)).fetchone()
    return meta,json.loads(row['content'])

def public_content(content):
    return {**content,'tasks':[{k:v for k,v in t.items() if k not in ('answer','answer_hash')} for t in content['tasks']], 'commands':list(content['commands'])}

def submit(db,user_id,unit_id,answers):
    db.execute('BEGIN IMMEDIATE')
    meta,c=accessible_unit(db,user_id,unit_id)
    if len(answers)!=len(c['tasks']): raise HTTPException(422,'Answer every question before submitting.')
    checks=[secrets.compare_digest(answer_digest(a),t['answer_hash']) for a,t in zip(answers,c['tasks'])]
    passed=all(checks)
    now=int(time.time())
    db.execute('INSERT INTO attempts(user_id,unit_id,correct,created) VALUES(?,?,?,?)',(user_id,unit_id,int(passed),now))
    awarded=0
    if passed:
        cur=db.execute('INSERT OR IGNORE INTO completions(user_id,unit_id,completed,xp) VALUES(?,?,?,?)',(user_id,unit_id,now,meta['xp']))
        awarded=meta['xp'] if cur.rowcount else 0
    return dict(passed=passed,checks=checks,xp_awarded=awarded,message='Mission complete. Your progress is saved.' if passed else 'Not quite yet. Review the marked findings and try again.')

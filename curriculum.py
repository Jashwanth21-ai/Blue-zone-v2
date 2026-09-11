"""Original BlueZone V1 curriculum. Answers are hashed before persistence."""
import json
from .db import connect
from .security import answer_digest

PATHS = [
 ('foundations','Security foundations','Understand the systems you will defend. Build confidence with networks, Linux, and the web.','Beginner',1),
 ('defender','The practical defender','Follow the evidence. Investigate traffic, fix access controls, and plan a response.','Intermediate',2),
 ('operations','Security operations','Connect signals, prioritize risk, and close a complete incident investigation.','Advanced',3),
]

def task(prompt, answer, hint, options=None):
    return dict(prompt=prompt, answer=answer, hint=hint, options=options or [])

def section(title, text):
    return dict(title=title, text=text)

def unit(id, path, title, summary, kind, minutes, xp, sections, tasks, evidence='', commands=None):
    return dict(id=id,path_id=path,title=title,summary=summary,kind=kind,minutes=minutes,xp=xp,
      content=dict(sections=sections,tasks=tasks,evidence=evidence,commands=commands or {}))

UNITS = [
 unit('network-basics','foundations','Follow a packet','Learn how an ordinary web request travels, and where security controls fit.','lesson',15,100,[
 section('Start with permission','Practice only on the supplied BlueZone evidence or systems whose owner has explicitly authorized you to test. These exercises use fictional hosts and reserved addresses. Your goal is to explain what happened and choose a defensible response.'),
 section('From a name to a connection','A browser asks a DNS resolver for the address of a hostname. It then connects to the destination address and service port. TCP establishes a reliable connection; TLS can protect application traffic in transit. HTTPS commonly uses TCP port 443. DNS resolution alone does not establish that a website is trustworthy.'),
 section('Think in layers','An IP address identifies a network destination. A port identifies a service endpoint on that host. A firewall can allow or deny traffic using those attributes. An application must still check who the user is and what they may access. An open port is an exposure to investigate, not proof of compromise.'),
 section('Three security goals','Confidentiality limits who can read information. Integrity protects information against unauthorized change. Availability keeps a service usable. TLS helps confidentiality and integrity in transit; it does not fix broken access control or protect a compromised endpoint.')
 ],[task('Which service resolves a hostname to an IP address?','DNS','Think about the step before the browser opens a connection.',['DNS','SSH','SMTP']),task('Which security goal is affected when an attacker changes a payment amount?','Integrity','Is the issue reading, changing, or making data unavailable?',['Availability','Confidentiality','Integrity'])]),
 unit('linux-permissions','foundations','A file open to everyone','Inspect a Linux permission snapshot and remove unnecessary access.','lab',20,150,[
 section('Read the permission bits','Linux permission strings show the object type followed by permissions for the owner, group, and everyone else. The letters r, w, and x mean read, write, and execute. A dash means the permission is absent. For files, read exposes contents; write allows modification.'),
 section('Choose least privilege','A secret used by one service account should not be readable by every user. A mode of 600 grants its owner read and write access while granting no permissions to the group or others. Permissions are only one layer: ownership, backups, process privileges, and secret rotation matter too.'),
 section('Your assignment','Use the simulated terminal to list files, inspect the current account, and read the permission notes. Identify the overexposed file. No command touches your computer; only the listed commands are supported.')
 ],[task('Which filename exposes a service secret to every local user?','service.env','Look for a secret-like file with an r in the last three positions.'),task('Which numeric mode grants only the owner read and write access?','600','Read is 4, write is 2, execute is 1. Add per permission group.')],commands={
 'whoami':'analyst', 'ls -l':'-rw-r--r-- service service 92 service.env\n-rw------- analyst analyst 180 notes.txt\n-rwxr-xr-x root root 410 healthcheck.sh',
 'cat notes.txt':'The service account owns service.env. It is the only account that needs to read or change it. A process restart is not needed to change file permissions.'}),
 unit('web-boundaries','foundations','Know your trust boundaries','Separate browser input from server authority.','lesson',15,100,[
 section('The browser is outside your boundary','A learner can edit a page, change a URL, or send a request without using your interface. Hiding an admin button is useful design but provides no authorization. The server must verify the session and the required permission for every protected action.'),
 section('Authentication versus authorization','Authentication establishes which account is making a request. Authorization decides whether that account can perform the action on this particular resource. Knowing an invoice ID must not grant access to the invoice. Check ownership or an explicit permission on the server.'),
 section('Treat data as data','Render untrusted text as text, not HTML. Use parameterized queries so input is not interpreted as SQL. Cookies that carry sessions should be HttpOnly, Secure over HTTPS, and appropriately SameSite. State-changing requests also need a CSRF defense.')
 ],[task('A user is signed in but reads another user’s private invoice. Which control is missing?','Authorization','A valid identity is not permission to access every object.',['Authentication','Authorization','DNS']),task('Where must the admin permission check run?','Server','The browser can be modified by its user.',['Browser only','Server','CSS'])]),
 unit('first-triage','foundations','The unusual sign-in','Distinguish an observation from a confirmed compromise.','challenge',20,200,[
 section('Establish a baseline','A useful investigation compares events with expected behavior. Failed sign-ins can be typing mistakes, broken automation, or an attack. Repeated failures followed by success deserve investigation, but do not establish that an account was compromised.'),
 section('Preserve what you know','Record timestamps, account identifiers, source addresses, and the exact event. Distinguish evidence from interpretation. Use the supplied UTC log below to identify the account requiring investigation. The CTF flag format is BZ{account}, using its account name.')
 ],[task('Submit the flag for the account with repeated failures followed by success.','BZ{mira}','Correlate the account name across failure and success events.'),task('Do these logs alone prove account compromise?','No','A legitimate user can also mistype a password.',['Yes','No'])],evidence='09:00Z user=lev src=192.0.2.10 result=success\n09:01Z user=mira src=198.51.100.8 result=failure\n09:02Z user=mira src=198.51.100.8 result=failure\n09:03Z user=mira src=198.51.100.8 result=failure\n09:04Z user=mira src=198.51.100.8 result=success'),
 unit('session-defense','defender','Protect the session','Design revocable authentication and object-level access checks.','lesson',20,150,[
 section('A session is a temporary credential','After checking a password, a server can issue a high-entropy random session token. Store a hash of that token in the database, associate it with the user, and give it an expiry. Possession of the token grants access, so keep it out of URLs and logs.'),
 section('Revocation is a feature','Logout should delete the session on the server, not merely clear the browser cookie. Password changes and account suspension should invalidate existing sessions. Evaluate account status on protected requests so a suspended account cannot continue using an old session.'),
 section('Defend writes','Cross-site request forgery causes a browser to send an authenticated request the user did not intend. Combine origin validation, SameSite cookies, and a session-bound token on writes. These protections do not replace authorization or XSS prevention.')
 ],[task('After account suspension, what should happen to existing sessions?','Revoke them','Changing only the sign-in form leaves an existing session usable.',['Keep them forever','Revoke them','Rename them']),task('Does CSRF protection replace an ownership check?','No','These controls address different threats.',['Yes','No'])]),
 unit('packet-analysis','defender','Find the unexpected destination','Read a packet summary and isolate traffic worth investigating.','lab',25,200,[
 section('Read a flow','A flow groups traffic by source, destination, protocol, and service ports. Compare destination, timing, and volume with an approved baseline. High volume can be a backup; rare destinations can be legitimate. An observation needs context before you label it malicious.'),
 section('Encrypted traffic still has metadata','TLS hides application contents from an ordinary network observer, but endpoints, timing, and byte counts remain useful. Do not claim to know the contents of encrypted payloads from a flow table alone.'),
 section('Your assignment','The inventory lists approved backup and update destinations. Inspect the supplied flow summary, identify the unapproved destination, and state what the evidence cannot establish. Use only the simulated commands.')
 ],[task('Which destination address is absent from the approved inventory?','203.0.113.77','Compare each destination with the inventory.'),task('Can this encrypted flow summary prove which files were sent?','No','Byte counts are metadata, not decrypted file contents.',['Yes','No'])],commands={
 'cat inventory.txt':'Approved destinations:\n192.0.2.20 backup service\n192.0.2.30 update mirror',
 'flows':'UTC     SOURCE      DESTINATION    PORT   BYTES\n10:00   10.0.0.8    192.0.2.30     443    4100\n10:05   10.0.0.8    192.0.2.20     443    830000\n10:07   10.0.0.8    203.0.113.77   443    920000',
 'cat capture-notes.txt':'All three flows use TLS. No decrypted application payload is included. The workstation owner reports no expected external upload.'}),
 unit('access-control','defender','Close the access gap','Review a vulnerable endpoint and choose a safe repair.','challenge',25,250,[
 section('Review the decision, not the button','The endpoint below returns an invoice using only the URL identifier. It has a signed-in user but never checks whether that user owns the invoice. Changing the identifier could expose another customer’s record.'),
 section('Repair the query boundary','Scope the database lookup to the authenticated owner: SELECT ... WHERE id = ? AND owner_id = ?. Use bound parameters. Return a consistent not-found response when an object is absent or inaccessible. Add a test with two accounts and prove that account A cannot read account B’s object.'),
 section('Avoid incomplete fixes','Random identifiers reduce guessing but do not enforce permission. Disabling a button has no effect on direct API requests. Logging a breach after it happens is not an access control.')
 ],[task('Which field must be checked against the authenticated user?','owner_id','The relationship between the resource and its owner is the missing decision.'),task('Which regression test is most useful?','Cross-account access is denied','Test the boundary the original code failed to enforce.',['The button is blue','Cross-account access is denied','The ID is long'])],evidence='def invoice(invoice_id, current_user):\n    return db.fetch("SELECT * FROM invoices WHERE id = ?", [invoice_id])\n\nSchema: invoices(id, owner_id, amount)\nCTF objective: identify the missing owner field and a test that prevents regression.'),
 unit('incident-response','defender','Contain, preserve, recover','Turn a suspicious event into a measured response.','lesson',20,150,[
 section('Containment is a tradeoff','Containment limits ongoing damage. Depending on evidence and business impact, isolate an endpoint or revoke a compromised session. Prefer reversible action that limits harm while preserving evidence. A destructive wipe can erase information needed to understand the incident.'),
 section('Preserve a useful record','Record UTC timestamps, evidence sources, hashes where applicable, collection steps, and custody. Avoid changing the original evidence. Work on copies and document uncertainties. Escalate decisions with business impact to the responsible owner.'),
 section('Recover with validation','Remove the cause, rotate exposed credentials, restore from a known-good state when needed, and verify that controls now work. Monitor for recurrence. A retrospective should explain both what happened and which control will prevent or detect the same pattern.')
 ],[task('Which action best preserves evidence during initial containment?','Isolate and preserve logs','Choose a reversible action that limits further communication.',['Wipe immediately','Isolate and preserve logs','Ignore all alerts']),task('What follows remediation?','Validate and monitor','A fix needs evidence that it works.',['Validate and monitor','Delete the timeline','Disable logging'])]),
 unit('threat-model','operations','Model the failure before it happens','Prioritize controls around an asset and a trust boundary.','lesson',25,200,[
 section('Start with the asset','A threat model is a structured argument about what could go wrong. Identify a valuable asset, the people and systems interacting with it, and the boundary across which trust changes. For a learning platform, account data and progress records are assets; the browser-to-API edge is a trust boundary.'),
 section('Make threats concrete','A useful threat names a trigger and an outcome: a learner changes a user ID in a progress request and reads another learner’s record. The control is a server-side ownership check. The validation is a cross-account request that is denied. This is more actionable than saying improve security.'),
 section('Prioritize exposure and impact','Assess likelihood and impact separately, then explain your uncertainty. A publicly reachable endpoint with missing authorization usually deserves attention before a low-impact internal cosmetic error. Record the owner, mitigation, and a test of the control.')
 ],[task('Which is a trust boundary?','Browser to API','Look for the point at which data comes from a less trusted party.',['Two headings on a page','Browser to API','Two colors']),task('What demonstrates that an ownership control works?','A denied cross-account request','Choose evidence of behavior, rather than intention.',['A policy title','A denied cross-account request','A hidden button'])]),
 unit('event-correlation','operations','Build the incident timeline','Correlate authentication, endpoint, and network evidence.','lab',30,300,[
 section('Normalize before joining','Use a common timezone and account for clock differences. Join records by stable host, account, or request identifiers. Adjacent timestamps alone do not establish causation. In this exercise all records use UTC and refer to the same workstation ID.'),
 section('Build and challenge a hypothesis','A successful sign-in followed by an unexpected process and unusual outbound traffic is stronger evidence than any signal alone. Still distinguish execution evidence from inferred intent. Record an alternative explanation and the evidence that would confirm or reject it.'),
 section('Your assignment','Read the three log sources. Identify the shared host and the earliest relevant event. Use the inventory to select a first containment action. These artifacts are fictional and read-only.')
 ],[task('Which host links the three sources?','ws-17','Compare the host identifiers, not just the times.'),task('What is the earliest relevant UTC timestamp?','11:01','Start with authentication before process and network events.')],commands={
 'cat auth.log':'11:01 UTC host=ws-17 user=mira event=login_success source=198.51.100.8',
 'cat endpoint.log':'11:03 UTC host=ws-17 user=mira process=unknown-helper parent=browser status=executed',
 'cat network.log':'11:05 UTC host=ws-17 destination=203.0.113.77 bytes=920000 tls=true',
 'cat inventory.txt':'ws-17 is a user workstation. unknown-helper is not approved. No scheduled upload exists. Initial containment can isolate ws-17 while preserving logs.'}),
 unit('hardening-review','operations','A release worth defending','Choose controls that close an exposed administration surface.','challenge',25,300,[
 section('Review the configuration','The configuration below describes a fictional staging deployment being prepared for release. Public administration, a universal shared credential, and unlimited authentication attempts combine into a high-priority exposure.'),
 section('Layer the controls','Require individual administrator accounts and explicit roles; restrict access where practical; revoke the shared credential. Add rate limits and audit sensitive actions. HTTPS protects transport but does not repair an authorization bypass. Validate the restrictions with unauthenticated and learner accounts.'),
 section('Capture the finding','Use the flag format BZ{setting_name} for the setting that permits unauthenticated administration. Then choose the regression test that directly checks the repair.')
 ],[task('Submit the flag for the setting that allows anonymous administration.','BZ{admin_public}','Read the administration access setting.'),task('Which check directly validates the repair?','Anonymous admin requests are denied','Test the permission boundary.',['The page loads faster','Anonymous admin requests are denied','The title changed'])],evidence='environment=staging\nhttps=true\nadmin_public=true\nshared_admin_password=true\nlogin_rate_limit=disabled\naudit_log=disabled'),
 unit('final-mission','operations','Operation Blue Horizon','Complete your final investigation: identify, contain, and validate.','capstone',45,500,[
 section('Mission briefing','You are the on-call defender for the fictional Horizon research team. An alert reports an unexpected outbound transfer. Your mission is to inspect the evidence, identify the affected host, find the exposed credential, and choose an evidence-preserving containment action. All timestamps are UTC.'),
 section('Investigation procedure','Read inventory.txt first, then compare auth.log, endpoint.log, and flows.csv. Look for shared identifiers and the first event in the sequence. Read config.txt to identify the exposed credential. The destination is a suspicious indicator in this scenario; it is not a real target to contact.'),
 section('Decision and validation','Contain the workstation and revoke the exposed credential. Preserve the logs and their provenance before remediation. After rotating the credential, verify that the old credential is rejected and that no unexpected egress recurs. The evidence supports an incident investigation, but encrypted byte counts alone do not establish which research files were transferred.'),
 section('Completion standard','Submit all five findings correctly. This practical capstone awards the Blue Horizon achievement and completes the V1 learning journey. Your completion record represents this curriculum, not an accredited professional certification.')
 ],[task('Affected workstation ID','ws-42','Join the host identifier across the three log sources.'),task('Suspicious destination IP','203.0.113.91','Compare the flow with the inventory’s approved destination.'),task('Exposed credential name','research_api_key','Read the configuration evidence; submit the name, not a value.'),task('Best initial action','Isolate workstation and revoke credential','Limit ongoing access while retaining investigation evidence.',['Wipe all servers','Isolate workstation and revoke credential','Publish the credential']),task('Final validation','Old credential rejected and egress monitored','Validate revocation and watch for recurrence.',['Old credential rejected and egress monitored','Disable monitoring','Keep the shared key'])],commands={
 'cat inventory.txt':'ws-42: research workstation, owner=mira\nApproved destination: 192.0.2.20 (backup)\nExternal uploads: none scheduled',
 'cat auth.log':'14:00 UTC host=ws-42 user=mira login=success source=198.51.100.9',
 'cat endpoint.log':'14:02 UTC host=ws-42 process=unapproved-sync accessed=config.txt',
 'cat flows.csv':'time,host,destination,port,bytes\n14:03,ws-42,203.0.113.91,443,4200000',
 'cat config.txt':'Credential name: research_api_key\nStorage: plaintext configuration, world-readable\nValue: [redacted from training evidence]\nLast rotation: unknown',
 'cat evidence-notes.txt':'Evidence is a fictional training snapshot. TLS payloads are unavailable. Preserve source logs, record UTC timestamps, isolate the host, and validate revocation.'})
]

def seed():
    with connect() as db:
        for p in PATHS:
            db.execute('INSERT OR IGNORE INTO paths VALUES(?,?,?,?,?)',p)
        for i,u in enumerate(UNITS,1):
            c=json.loads(json.dumps(u['content']))
            for t in c['tasks']:
                t['answer_hash']=answer_digest(t.pop('answer'))
            db.execute('INSERT OR IGNORE INTO units(id,path_id,title,summary,kind,minutes,xp,position,content) VALUES(?,?,?,?,?,?,?,?,?)',
              (u['id'],u['path_id'],u['title'],u['summary'],u['kind'],u['minutes'],u['xp'],i,json.dumps(c)))

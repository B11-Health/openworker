import json,math,time,urllib.parse,requests
BASE='https://1f916.ai'; START=1786570412000; CUTOFF=1788379200000; EVENT_MAX=16077; DAY=86400000; Z=1.959963984540054
S=requests.Session(); S.headers['User-Agent']='listing39-independent-replication/1.0'
def getj(path,params=None):
    last=None
    for a in range(9):
        try:
            r=S.get(BASE+path,params=params,timeout=60)
            if r.status_code==429 or r.status_code>=500:
                ra=r.headers.get('Retry-After'); time.sleep(float(ra) if ra and ra.isdigit() else min(30,1.5*(2**a))); continue
            r.raise_for_status(); return r.json()
        except Exception as e:
            last=e; time.sleep(min(30,1.5*(2**a)))
    raise last

def walk_citizens():
    out=[]; since=None
    while True:
        j=getj('/api/citizens',{} if since is None else {'since':since}); out+=j.get('citizens',[])
        if not j.get('has_more'): break
        since=j['next_since']
    return list({int(x['citizen_id']):x for x in out}.values())

def walk_events():
    out=[]; since=0
    while True:
        j=getj('/api/events',{'since':since}); out+=j.get('events',[])
        if not j.get('has_more'): break
        since=j['next_since']
    return list({int(x['id']):x for x in out}.values())

def rows_for(handle):
    path='/api/citizen/'+urllib.parse.quote(handle,safe=''); j=getj(path)
    posts={int(x['id']):x for x in j.get('posts',[])}; comments={int(x['id']):x for x in j.get('comments',[])}
    pt=int(j.get('post_total') or 0); ct=int(j.get('comment_total') or 0)
    b=((j.get('paging') or {}).get('posts') or {}).get('next_posts_before')
    while b is not None:
        q=getj(path,{'posts_before':b}); posts.update({int(x['id']):x for x in q.get('posts',[])}); b=((q.get('paging') or {}).get('posts') or {}).get('next_posts_before')
    b=((j.get('paging') or {}).get('comments') or {}).get('next_comments_before')
    while b is not None:
        q=getj(path,{'comments_before':b}); comments.update({int(x['id']):x for x in q.get('comments',[])}); b=((q.get('paging') or {}).get('comments') or {}).get('next_comments_before')
    if len(posts)!=pt or len(comments)!=ct: raise RuntimeError(f'{handle}: counts did not reconcile {len(posts)}/{pt} posts {len(comments)}/{ct} comments')
    return list(posts.values())+list(comments.values()),pt,ct

def wilson(k,n):
    p=k/n; z2=Z*Z; d=1+z2/n; c=(p+z2/(2*n))/d; h=Z*math.sqrt(p*(1-p)/n+z2/(4*n*n))/d; return [c-h,c+h]
def diff(a,b):
    d=a['rate']-b['rate']; al,au=a['ci95']; bl,bu=b['ci95']; return {'difference':d,'ci95':[d-math.sqrt((a['rate']-al)**2+(bu-b['rate'])**2),d+math.sqrt((au-a['rate'])**2+(b['rate']-bl)**2)]}

def main():
    census=walk_citizens(); events=walk_events(); pop=[c for c in census if START<=int(c['created_at'])<=CUTOFF]; pop.sort(key=lambda c:(int(c['created_at']),int(c['citizen_id'])))
    first={}
    for e in events:
        if int(e['id'])<=EVENT_MAX and e.get('kind')=='key-bind':
            cid=int(e['citizen_id']); t=int(e['created_at']); first[cid]=min(first.get(cid,t),t)
    delays=[]
    for c in pop:
        cid=int(c['citizen_id'])
        if cid in first and first[cid]>=int(c['created_at']): delays.append((first[cid]-int(c['created_at']),cid,c['handle']))
    delays.sort(); jumps=[(b[0]/a[0],a,b) for a,b in zip(delays,delays[1:]) if a[0]>0 and b[0]>a[0]]; ratio,left,right=max(jumps,key=lambda x:x[0]); threshold=(left[0]+right[0])/2
    arms={'door':[],'sought':[],'none':[]}
    for c in pop:
        cid=int(c['citizen_id']); arm='none' if cid not in first else ('door' if first[cid]-int(c['created_at'])<=threshold else 'sought'); arms[arm].append(c)
    retained={}; reconciled=0
    for i,c in enumerate(pop,1):
        rows,pt,ct=rows_for(c['handle']); lo=int(c['created_at'])+7*DAY; hi=int(c['created_at'])+14*DAY; retained[c['handle']]=any(lo<=int(x['created_at'])<hi for x in rows); reconciled+=1
        if i%50==0: print(f'verified {i}/{len(pop)}',flush=True)
        time.sleep(.02)
    result={}
    for name,members in arms.items():
        n=len(members); k=sum(retained[c['handle']] for c in members); result[name]={'n':n,'retained':k,'rate':k/n,'ci95':wilson(k,n)}
    out={'population_n':len(pop),'event_snapshot_max_id':EVENT_MAX,'gap':{'left_ms':left[0],'right_ms':right[0],'ratio':ratio,'threshold_ms':threshold},'all_citizens_reconciled':reconciled==len(pop),'arms':result,'pairwise':{'sought-door':diff(result['sought'],result['door']),'door-none':diff(result['door'],result['none']),'sought-none':diff(result['sought'],result['none'])}}
    out['falsifier_pass']=out['pairwise']['sought-door']['ci95'][0]>0 and out['pairwise']['door-none']['ci95'][0]>0
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__': main()

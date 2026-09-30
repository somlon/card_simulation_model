import random, sys, time, json
import deck as D
from search import SearchAI, new_game
from policy import LearnedAI
a,_,_=D.load('decks/시제_번성충_대발생.deck'); b,_,_=D.load('decks/시제_솔루나_아츠.deck')
who=int(sys.argv[1]); n=int(sys.argv[2]); start=int(sys.argv[3]); R=int(sys.argv[4]); M=int(sys.argv[5])
out=[]; t=time.time(); st={'decisions':0,'searched':0,'rollouts':0,'desync':0,'time':0.0}
for i in range(start,start+n):
    first=i%2
    s_ai=SearchAI([a,b][who]['스킬'],rollouts=R,max_cands=M)
    ais=[s_ai, LearnedAI(b['스킬'],learn=False)] if who==0 else [LearnedAI(a['스킬'],learn=False), s_ai]
    g=new_game([a,b],ais,first,10000+i,[])
    w,_=g.run(); out.append((first,w))
    for k in st: st[k]+=s_ai.stats[k]
json.dump({'out':out,'stats':st,'sec':time.time()-t}, open(f'es_{who}_{start}.json','w'))
print(who, start, sum(1 for f,w in out if w==who),'/',len(out), f'{time.time()-t:.0f}s', st)

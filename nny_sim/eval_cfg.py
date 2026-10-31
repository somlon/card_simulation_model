import sys, time, json
import deck as D
from search import SearchAI, new_game
from policy import LearnedAI
a,_,_=D.load('decks/시제_번성충_대발생.deck'); b,_,_=D.load('decks/시제_솔루나_아츠.deck')
tag=sys.argv[1]; n=int(sys.argv[2]); start=int(sys.argv[3]); R=int(sys.argv[4]); M=int(sys.argv[5]); key=sys.argv[6]=='1'; depth=None if sys.argv[7]=='-' else int(sys.argv[7])
mode=sys.argv[8]  # B: 탐색 번성충 vs 학습 솔루나 / SS: 탐색 vs 탐색
out=[]; t=time.time()
for i in range(start,start+n):
    mk=lambda sk: SearchAI(sk,R,M,key_only=key,depth=depth)
    ais=[mk(a['스킬']), LearnedAI(b['스킬'],learn=False)] if mode=='B' else [mk(a['스킬']), mk(b['스킬'])]
    g=new_game([a,b],ais,i%2,30000+i,[]); w,_=g.run(); out.append((i%2,w))
    if time.time()-t>265: break
json.dump(out,open(f'cfg_{tag}_{start}.json','w'))
print(tag,len(out),'판 번성충',sum(w==0 for f,w in out),f'{(time.time()-t)/len(out):.2f}s/판')

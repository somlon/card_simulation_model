import sys, time, json
import deck as D
from search import SearchAI, new_game
a,_,_=D.load('decks/시제_번성충_대발생.deck'); b,_,_=D.load('decks/시제_솔루나_아츠.deck')
n=int(sys.argv[1]); start=int(sys.argv[2]); out=[]; t=time.time()
for i in range(start,start+n):
    g=new_game([a,b],[SearchAI(a['스킬'],6,3),SearchAI(b['스킬'],6,3)],i%2,20000+i,[])
    w,_=g.run(); out.append((i%2,w))
    if time.time()-t>270: break
json.dump(out,open(f'ss_{start}.json','w')); print(start,len(out),sum(w==0 for f,w in out),f'{time.time()-t:.0f}s')

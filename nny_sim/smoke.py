import random, itertools, traceback, sys, glob, collections, time
from engine import Game
from cards import Impl
import policy as P, deck as D
from run import fmt
decks=[D.load(f)[0] for f in sorted(glob.glob('decks/시제_*.deck'))]
N=int(sys.argv[1]); rng=random.Random(1); errs=0; t=time.time()
res={}
for a,b in itertools.combinations(range(len(decks)),2):
    w=[0,0]; turns=[]
    for i in range(N):
        log=[]
        try:
            g=Game([decks[a],decks[b]],[P.LearnedAI(decks[a]['스킬'],learn=False),P.LearnedAI(decks[b]['스킬'],learn=False)],i%2,rng,log,Impl)
            x,_=g.run(); turns.append(g.turn)
            if x is not None: w[x]+=1
        except Exception:
            errs+=1
            if errs<=4: open(f'err_{errs}.txt','w').write(f'{decks[a]["이름"]} vs {decks[b]["이름"]}\n'+traceback.format_exc()+'\n'+fmt(log[-60:]))
    res[(a,b)]=w
    print(f'{decks[a]["스킬"]:>14} vs {decks[b]["스킬"]:<14} {w[0]}-{w[1]}  평균 {sum(turns)/max(1,len(turns)):.1f}턴', flush=True)
print('errors',errs, f'{time.time()-t:.0f}s')

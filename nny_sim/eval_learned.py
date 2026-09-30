import random, sys, collections
from engine import Game
from cards import Impl
from ai import HeuristicAI
import policy as P, deck as D
from run import play_match
a,_,_=D.load(sys.argv[1]); b,_,_=D.load(sys.argv[2]); N=int(sys.argv[3])
rng=random.Random(2027)
def single(mkA, mkB, n):
    w={0:[0,0],1:[0,0]}
    for i in range(n):
        f=i%2; x,_=Game([a,b],[mkA(),mkB()],f,rng,[],Impl).run()
        if x is None: continue
        w[f][0]+= x==0; w[f][1]+=1
    tot=(w[0][0]+w[1][0])/(w[0][1]+w[1][1])
    return f'번성충 {tot*100:.1f}% (번성충 선공 {w[0][0]/w[0][1]*100:.1f}% / 후공 {w[1][0]/w[1][1]*100:.1f}%)'
LA=lambda: P.LearnedAI(a['스킬'],learn=False); LB=lambda: P.LearnedAI(b['스킬'],learn=False)
HA=lambda: HeuristicAI(a['스킬']); HB=lambda: HeuristicAI(b['스킬'])
print('휴리스틱 vs 휴리스틱 :', single(HA,HB,N))
print('학습 번성충 vs 휴리스틱 솔루나:', single(LA,HB,N))
print('휴리스틱 번성충 vs 학습 솔루나:', single(HA,LB,N))
print('학습 vs 학습          :', single(LA,LB,N))

import random, time, traceback, sys, collections
from run import play_match, fmt
import deck as D
dA,_,_=D.load(sys.argv[1]); dB,_,_=D.load(sys.argv[2]); N=int(sys.argv[3]); seed=int(sys.argv[4]) if len(sys.argv)>4 else 7
rng=random.Random(seed); t=time.time()
from report import Report
rep=Report()
stat=collections.Counter(); errs=0; turns=[]; reasons=collections.Counter()
for i in range(N):
    log=[]
    try:
        mw, rounds = play_match(dA,dB,i%2,rng,log)
    except Exception as e:
        errs+=1
        if errs<=3:
            open(f'err_{errs}.txt','w').write(traceback.format_exc()+'\n'+fmt(log[-80:]))
        continue
    stat['match',mw]+=1
    for r in rounds:
        rep.add(log[r['log'][0]:r['log'][1]], [dA['이름'], dB['이름']], r['winner'], r['reason'])
        stat['game',r['winner']]+=1; stat['game_first',r['first'],r['winner']]+=1; turns.append(r['turns']); reasons[r['reason'].split(' ')[-1] if 'HP' not in r['reason'] else 'HP 0']+=1
import policy as P, match as M; P.POLICY.save(); M.SIDE.save()
print(f'{N} matches {time.time()-t:.1f}s errors={errs}')
print(dict(stat)); print('avg turns',sum(turns)/max(1,len(turns))); print(reasons)
txt=rep.text()
open('시뮬레이션_보고서.md','w',encoding='utf-8').write(f'# 시뮬레이션 종료 보고서\n\n{dA["이름"]} vs {dB["이름"]} · {N}매치\n\n'+txt)
print(txt)

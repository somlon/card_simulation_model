import random, re, sys, collections
from run import play_match
import deck as D
dA,_,_=D.load(sys.argv[1]); dB,_,_=D.load(sys.argv[2])
rng=random.Random(3); cnt=collections.Counter(); ss=collections.Counter()
for i in range(200):
    log=[]; play_match(dA,dB,i%2,rng,log)
    for e in log:
        m=re.search(r'「([^」]+)」 (\d)번 효과 발동',e['m'])
        if m: cnt[m.group(1)+'#'+m.group(2)]+=1
        m=re.search(r'「([^」]+)」 (특수소환|일반소환)',e['m'])
        if m: ss[m.group(1)+' '+m.group(2)]+=1
        if '무효' in e['m'] and '효과 무효' in e['m']: cnt['(무효 발생)']+=1
for k,v in sorted(cnt.items(), key=lambda x:-x[1]): print(f'{v:5d} {k}')
print('---'); 
for k,v in sorted(ss.items(), key=lambda x:-x[1]): print(f'{v:5d} {k}')

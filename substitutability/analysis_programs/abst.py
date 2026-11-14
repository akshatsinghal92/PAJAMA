import numpy as np, pipeline as P, warnings, collections; warnings.filterwarnings("ignore")
from sklearn.metrics import accuracy_score
progs=P.load_programs_from_dir("programs_synth_v2")
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); rl=P.load_jsonl("data_synth_v2/pajama/real_external.jsonl")
pipe=P.fit(val,progs); yv,yt,yr=map(P.labels_of,(val,te,rl))
Sv,St,Sr=[P.collect_scores(d,progs) for d in (val,te,rl)]
th=pipe.best_thresholds; norm=lambda S:np.nan_to_num(P.normalize(S,pipe.norm_params),nan=.5)
Nv,Nt,Nr=map(norm,(Sv,St,Sr))
# default value = most common raw score on val, if it covers >=30% of val rows
dflt=[]
for c in range(Sv.shape[1]):
    v,n=collections.Counter(np.round(Sv[:,c],4)).most_common(1)[0]; dflt.append(v if n/len(Sv)>=.3 else None)
print("programs given an abstain-on-default rule:",sum(d is not None for d in dflt))
def L(N,S):
    M=(N>=th[None,:]).astype(int)
    for c,d in enumerate(dflt):
        if d is not None: M[np.round(S[:,c],4)==d,c]=-1
    return M
Mv,Mt,Mr=L(Nv,Sv),L(Nt,St),L(Nr,Sr)
cov_acc=np.array([accuracy_score(yv[Mv[:,c]!=-1],Mv[Mv[:,c]!=-1,c]) if (Mv[:,c]!=-1).sum()>20 else 0 for c in range(80)])
ranked=[int(i) for i in np.argsort(cov_acc)[::-1] if cov_acc[i]>=.5]
rng=np.random.RandomState(0)
def full(lm,M,y):
    h=lm.predict(L=M,tie_break_policy="random"); h=np.where(h==-1,rng.randint(0,2,len(h)),h); return (h==y).mean()
best=(-1,None)
for k in range(1,len(ranked)+1):
    cols=ranked[:k]
    try: lm=P._fit_label_model(Mv[:,cols],yv if k>=3 else None,epochs=200)
    except Exception: continue
    h=lm.predict(L=Mv[:,cols],tie_break_policy="random"); v=h!=-1
    a=accuracy_score(yv[v],h[v]) if v.sum() else 0
    if a>best[0]: best=(a,k)
k=best[1]; cols=ranked[:k]; lm=P._fit_label_model(Mv[:,cols],yv if k>=3 else None,epochs=500)
print(f"chosen k={k} (val {best[0]:.3f}); test acc {full(lm,Mt[:,cols],yt):.4f}  real acc {full(lm,Mr[:,cols],yr):.4f}")
print("rows where every chosen program abstains (random fill): test",(Mt[:,cols]==-1).all(1).mean().round(3),"real",(Mr[:,cols]==-1).all(1).mean().round(3))
for k2 in (10,20,40):
    c2=ranked[:k2]; lm2=P._fit_label_model(Mv[:,c2],yv,epochs=500)
    print(f"  k={k2}: test {full(lm2,Mt[:,c2],yt):.4f}  real {full(lm2,Mr[:,c2],yr):.4f}")

import numpy as np, pipeline as P, warnings; warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
progs=P.load_programs_from_dir("programs_synth_v2")
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); re_=P.load_jsonl("data_synth_v2/pajama/real_external.jsonl")
pipe=P.fit(val,progs); print("best_k",pipe.best_k)
yv,yt,yr=map(P.labels_of,(val,te,re_))
Sv=P.collect_scores(val,progs); nv=P.normalize(Sv,pipe.norm_params)
nt=P.normalize(P.collect_scores(te,progs),pipe.norm_params); nr=P.normalize(P.collect_scores(re_,progs),pipe.norm_params)
ranked=[int(i) for i in np.argsort(pipe.best_accuracies)[::-1] if pipe.best_accuracies[i]>=0.5]
print("surviving",len(ranked),"val acc top/median/last",pipe.best_accuracies[ranked[0]],np.median(pipe.best_accuracies[ranked]),pipe.best_accuracies[ranked[-1]])
rng=np.random.RandomState(0)
def acc(M,y,lm=None,vote=False):
    if vote:
        v=np.where(M==-1,np.nan,M).astype(float); p=np.nanmean(v,1); p=np.where(np.isnan(p),.5,p)
        h=(p>.5).astype(int); h[p==.5]=rng.randint(0,2,(p==.5).sum())
    else:
        h=lm.predict(L=M,tie_break_policy="random")
        h=np.where(h==-1,rng.randint(0,2,len(h)),h)
    return round(float((h==y).mean()),4)
print("k  | snorkel test/real | majority-vote test/real")
for k in (1,3,5,8,12,20,40,len(ranked)):
    cols=ranked[:k]
    Mv=P.build_label_matrix(nv,cols,pipe.best_thresholds,0.0)
    lm=P._fit_label_model(Mv,yv if k>=3 else None,epochs=200)
    Mt=P.build_label_matrix(nt,cols,pipe.best_thresholds,0.0); Mr=P.build_label_matrix(nr,cols,pipe.best_thresholds,0.0)
    print(k,"|",acc(Mt,yt,lm),acc(Mr,yr,lm),"|",acc(Mt,yt,vote=True),acc(Mr,yr,vote=True))
# supervised on all votes: learn from val, ceiling check
Vv=P.build_label_matrix(nv,ranked,pipe.best_thresholds,0.0); Vt=P.build_label_matrix(nt,ranked,pipe.best_thresholds,0.0); Vr=P.build_label_matrix(nr,ranked,pipe.best_thresholds,0.0)
for name,(Xv,Xt,Xr) in {"LogReg on all 78 votes":(Vv,Vt,Vr),"LogReg on all 78 raw scores":(np.nan_to_num(nv,nan=.5),np.nan_to_num(nt,nan=.5),np.nan_to_num(nr,nan=.5))}.items():
    m=LogisticRegression(C=0.3,max_iter=2000).fit(Xv,yv); print(name,"val-fit -> test",round(m.score(Xt,yt),4),"real",round(m.score(Xr,yr),4))

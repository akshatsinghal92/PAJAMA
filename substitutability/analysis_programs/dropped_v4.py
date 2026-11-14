import numpy as np, pipeline as P, json, warnings, collections; warnings.filterwarnings("ignore")
progs=P.load_programs_from_dir("programs_synth_v4"); man={e["program_id"]:e for e in json.load(open("programs_synth_v4/manifest.json"))}
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); re_=P.load_jsonl("data_synth_v2/pajama/real_external.jsonl")
pipe=P.fit(val,progs); yv,yt,yr=map(P.labels_of,(val,te,re_))
nv=P.normalize(P.collect_scores(val,progs),pipe.norm_params); nt=P.normalize(P.collect_scores(te,progs),pipe.norm_params); nr=P.normalize(P.collect_scores(re_,progs),pipe.norm_params)
th=pipe.best_thresholds
pv=(np.nan_to_num(nv,nan=.5)>=th).astype(int); pt=(np.nan_to_num(nt,nan=.5)>=th).astype(int); pr=(np.nan_to_num(nr,nan=.5)>=th).astype(int)
va=(pv==yv[:,None]).mean(0); ta=(pt==yt[:,None]).mean(0); ra=(pr==yr[:,None]).mean(0)
ids=[p.program_id for p in progs]; ranked=[int(i) for i in np.argsort(pipe.best_accuracies)[::-1] if pipe.best_accuracies[i]>=0.5]
sel=set(ranked[:pipe.best_k])
print("check val acc equals pipe.best_accuracies:",np.allclose(va,pipe.best_accuracies,atol=1e-3))
rows=[]
for rank,c in enumerate(ranked,1):
    rows.append(dict(rank=rank,id=ids[c],rub=man[ids[c]]["heuristic_name"],val=round(va[c],3),test=round(ta[c],3),real=round(ra[c],3),yes=round(pt[:,c].mean(),2),sel=c in sel))
json.dump(rows,open("analysis_programs/out_v4/dropped_rows.json","w"))
for r in rows: print(r)
T=np.array([r["test"] for r in rows]); V=np.array([r["val"] for r in rows]); S=np.array([r["sel"] for r in rows])
print("corr val/test",round(np.corrcoef(V,T)[0,1],3))
best6=set(np.argsort(-T)[:6]); print("test-top6 ranks",sorted(int(i)+1 for i in best6))
for cut in (0.70,0.72): print(f"dropped with test>={cut}:",int(((T>=cut)&~S).sum()),"of",int((T>=cut).sum()))
print("selected test min",T[S].min(),"dropped test max",T[~S].max())
print("val acc buckets:",collections.Counter(("<.55" if v<.55 else "<.60" if v<.6 else "<.65" if v<.65 else "<.70" if v<.7 else ">=.70") for v in V))
print("test acc buckets:",collections.Counter(("<.55" if v<.55 else "<.60" if v<.6 else "<.65" if v<.65 else "<.70" if v<.7 else ">=.70") for v in T))
# k sweep with snorkel as pipeline does + test
rng=np.random.RandomState(0)
def pred(lm,M):
    h=lm.predict(L=M,tie_break_policy="random"); return np.where(h==-1,rng.randint(0,2,len(h)),h)
print("k | val agree(pipeline) | test | real")
for k in list(range(1,13))+[15,20,25,30,40,50,60,70,len(ranked)]:
    cols=ranked[:k]
    Mv=P.build_label_matrix(nv,cols,th,0.0); lm=P._fit_label_model(Mv,yv if k>=3 else None,epochs=P.SNORKEL_EPOCHS)
    a=(pred(lm,Mv)==yv).mean(); t=(pred(lm,P.build_label_matrix(nt,cols,th,0.0))==yt).mean(); r=(pred(lm,P.build_label_matrix(nr,cols,th,0.0))==yr).mean()
    print(k,round(a,4),round(t,4),round(r,4))
# oracle: best test-ranked 6/11
for k in (6,11,20):
    cols=[ranked[i] for i in np.argsort(-T)[:k]]
    Mv=P.build_label_matrix(nv,cols,th,0.0); lm=P._fit_label_model(Mv,yv,epochs=P.SNORKEL_EPOCHS)
    print("oracle top",k,"by TEST acc -> test",round((pred(lm,P.build_label_matrix(nt,cols,th,0.0))==yt).mean(),4))
# diversity: one best-val per rubric (20)
br={}
for c in ranked:
    h=man[ids[c]]["heuristic_id"]; br.setdefault(h,c)
cols=list(br.values()); Mv=P.build_label_matrix(nv,cols,th,0.0); lm=P._fit_label_model(Mv,yv,epochs=P.SNORKEL_EPOCHS)
print("best-per-rubric (20) -> test",round((pred(lm,P.build_label_matrix(nt,cols,th,0.0))==yt).mean(),4),"real",round((pred(lm,P.build_label_matrix(nr,cols,th,0.0))==yr).mean(),4))

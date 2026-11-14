import numpy as np, pipeline as P, json, warnings; warnings.filterwarnings("ignore")
progs=P.load_programs_from_dir("programs_synth_v4"); man={e["program_id"]:e for e in json.load(open("programs_synth_v4/manifest.json"))}
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl")
pipe=P.fit(val,progs); th=pipe.best_thresholds; ids=[p.program_id for p in progs]
rub=np.array([man[i]["heuristic_id"] for i in ids]); SEL=[76,17,6,52,65,29]
real=np.array([i not in (8,61) for i in ids])
def stats(rows,name):
    y=P.labels_of(rows); n=P.normalize(P.collect_scores(rows,progs),pipe.norm_params)
    p=(np.nan_to_num(n,nan=.5)>=th).astype(int)[:,real]; I=np.array(ids)[real]; R=rub[real]; m=p.shape[1]
    A=(p[:,:,None]==p[:,None,:]).mean(0)
    q=p.mean(0); pe=q[:,None]*q[None,:]+(1-q[:,None])*(1-q[None,:]); K=(A-pe)/(1-pe)
    E=(p!=y[:,None]); inter=(E[:,:,None]&E[:,None,:]).sum(0); uni=(E[:,:,None]|E[:,None,:]).sum(0); J=inter/np.maximum(uni,1)
    # conditional: P(j wrong | i wrong)
    C=inter/np.maximum(E.sum(0)[:,None],1)
    off=~np.eye(m,dtype=bool); same=(R[:,None]==R[None,:])&off; diff=(R[:,None]!=R[None,:])
    s=[list(I).index(i) for i in SEL]; so=~np.eye(len(s),dtype=bool)
    print(f"\n===== {name}: {len(rows)} rows, {m} programs (placeholders 8, 61 excluded) =====")
    print("                         agreement  kappa  error-Jaccard  P(j wrong | i wrong)")
    for lab,mask in (("all pairs",off),("same rubric",same),("different rubric",diff)):
        print(f"  {lab:22s} {A[mask].mean():8.3f} {K[mask].mean():6.3f} {J[mask].mean():12.3f} {C[mask].mean():12.3f}")
    print(f"  {'selected 6':22s} {A[np.ix_(s,s)][so].mean():8.3f} {K[np.ix_(s,s)][so].mean():6.3f} {J[np.ix_(s,s)][so].mean():12.3f} {C[np.ix_(s,s)][so].mean():12.3f}")
    print("  agreement distribution over pairs: min %.3f  p10 %.3f  median %.3f  p90 %.3f  max %.3f"%tuple(np.percentile(A[off],[0,10,50,90,100])))
    print("  pairs with agreement >=0.90:",int((A[off]>=.9).sum()//2),"  >=0.85:",int((A[off]>=.85).sum()//2),"  <0.60:",int((A[off]<.6).sum()//2),"of",m*(m-1)//2)
    k=p.sum(1); print("  rows where ALL 78 agree:",int(((k==0)|(k==m)).sum()),f"({((k==0)|(k==m)).mean():.1%})","  where >=90% agree:",int((np.maximum(k,m-k)>=.9*m).sum()),f"({(np.maximum(k,m-k)>=.9*m).mean():.1%})")
    wr=E.sum(1); print("  rows wrong for ALL 78:",int((wr==m).sum()),"  wrong for >=80%:",int((wr>=.8*m).sum()),f"({(wr>=.8*m).mean():.1%})","  right for all:",int((wr==0).sum()))
    sp=p[:,s]; ks=sp.sum(1); es=E[:,s]
    print("  selected 6: rows unanimous",f"{((ks==0)|(ks==6)).mean():.1%}","  committee-majority errors where all 6 wrong:",int((es.sum(1)==6).sum()))
    out=[]
    for c in range(m):
        o=off[c]; out.append(dict(id=int(I[c]),rubric=man[int(I[c])]["heuristic_name"],acc=round(float(1-E[:,c].mean()),3),yes=round(float(q[c]),2),
            mean_agree=round(float(A[c][o].mean()),3),max_agree=round(float(A[c][o].max()),3),most_similar=int(I[o][A[c][o].argmax()]),mean_kappa=round(float(K[c][o].mean()),3)))
    out.sort(key=lambda r:-r["mean_agree"])
    print("  most 'typical' programs (highest mean agreement):"); [print("   ",r) for r in out[:5]]
    print("  most 'different' programs (lowest mean agreement):"); [print("   ",r) for r in out[-8:]]
    # rubric x rubric mean agreement
    rr=sorted(set(R)); M=np.array([[A[np.ix_(R==a,R==b)][(off[np.ix_(R==a,R==b)])].mean() for b in rr] for a in rr])
    print("  per-rubric: within-rubric agreement / mean agreement with other rubrics")
    for i,a in enumerate(rr): print(f"    {a:2d} {man[[x for x in ids if man[x]['heuristic_id']==a][0]]['heuristic_name'][:36]:36s} {M[i,i]:.3f}  {np.mean([M[i,j] for j in range(len(rr)) if j!=i]):.3f}")
    json.dump(out,open(f"analysis_programs/out_v4/agreement_{name}.json","w"),indent=1)
    np.save(f"analysis_programs/out_v4/agreement_matrix_{name}.npy",A)
    return A
Av=stats(val,"val"); At=stats(te,"test")
off=~np.eye(Av.shape[0],dtype=bool); print("\ncorr of pairwise agreement val vs test:",round(np.corrcoef(Av[off],At[off])[0,1],3))

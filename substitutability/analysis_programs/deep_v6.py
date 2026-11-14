import numpy as np, pipeline as P, json, warnings, collections, re; warnings.filterwarnings("ignore")
SP="analysis_programs/out_v6/"
progs=P.load_programs_from_dir("programs_synth_v6")
man={e["program_id"]:e for e in json.load(open("programs_synth_v6/manifest.json"))}
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl")
pipe=P.fit(val,progs); y=P.labels_of(te)
S=P.collect_scores(te,progs); np.save(SP+"S_test.npy",S)
N=P.normalize(S,pipe.norm_params); N=np.nan_to_num(N,nan=.5)
pred=(N>=pipe.best_thresholds[None,:]).astype(int)   # rows x 80
np.save(SP+"pred_test.npy",pred)
tok=lambda s:set(re.findall(r"[a-z]+",s.lower()))
STOP={"g","raw","fresh","and","or","of","with","the","a","in","for"}
def jac(r):
    a=tok(r["ingredient"])-STOP; b=tok(r["usda_match"])-STOP
    return len(a&b)/max(1,len(a|b))
J=np.array([jac(r) for r in te])
# head-noun overlap: does the first token of usda match appear in ingredient?
first=np.array([ (re.findall(r"[a-z]+",r["usda_match"].lower()) or [""])[0] in tok(r["ingredient"]) for r in te])
ulen=np.array([len(r["usda_match"].split(",")) for r in te])
print("PER-PROGRAM score behaviour")
rows=[]
for c,p in enumerate(progs):
    s=S[:,c]; u=len(np.unique(np.round(s,4)))
    corrJ=np.corrcoef(N[:,c],J)[0,1] if N[:,c].std()>0 else np.nan
    corrY=np.corrcoef(N[:,c],y)[0,1] if N[:,c].std()>0 else np.nan
    mode_share=collections.Counter(np.round(s,4)).most_common(1)[0][1]/len(s)
    rows.append(dict(id=p.program_id,rub=man[p.program_id]["heuristic_name"][:22],uniq=u,mode=round(mode_share,2),
      yes=round(pred[:,c].mean(),2),acc=round((pred[:,c]==y).mean(),3),rJ=round(corrJ,2),rY=round(corrY,2),
      th=pipe.best_thresholds[c]))
json.dump(rows,open(SP+"deep_rows.json","w"))
rJ=np.array([r["rJ"] for r in rows]); rY=np.array([r["rY"] for r in rows])
print("median corr(score, word-overlap)",np.nanmedian(rJ)," median corr(score,label)",np.nanmedian(rY))
print("corr(word overlap, label) itself:",round(np.corrcoef(J,y)[0,1],3))
print("programs with corr to overlap > corr to label:",int(np.sum(rJ>rY)),"/80")
print("programs with >=50% rows at one score value:",sum(r["mode"]>=.5 for r in rows))
print("corr across programs: acc vs rJ",round(np.corrcoef([r["acc"] for r in rows],rJ)[0,1],2),"acc vs mode-share",round(np.corrcoef([r["acc"] for r in rows],[r["mode"] for r in rows])[0,1],2))
# how many programs wrong per row
wrongfrac=(pred!=y[:,None]).mean(1)
np.save(SP+"wrongfrac.npy",wrongfrac)
print("\nROWS: share of programs wrong per row: mean",wrongfrac.mean().round(3))
for lab in (0,1):
    for lo,hi in ((0,.2),(.2,.5),(.5,.8),(.8,1.01)):
        m=(y==lab)&(J>=lo)&(J<hi); 
        if m.sum(): print(f"  label={lab} overlap[{lo},{hi}) n={m.sum():4d}  avg share of programs wrong={wrongfrac[m].mean():.2f}")
print("first USDA word in ingredient? label=1:",{k:round(wrongfrac[(y==1)&(first==k)].mean(),2) for k in (True,False)},"n",{k:int(((y==1)&(first==k)).sum()) for k in (True,False)})
print("first USDA word in ingredient? label=0:",{k:round(wrongfrac[(y==0)&(first==k)].mean(),2) for k in (True,False)},"n",{k:int(((y==0)&(first==k)).sum()) for k in (True,False)})
rc=collections.defaultdict(list)
for r,w in zip(te,wrongfrac): rc[r["relation_code"]].append(w)
print("avg share of programs wrong by pair type:",sorted(((k,round(np.mean(v),2),len(v)) for k,v in rc.items()),key=lambda x:-x[1]))
print("rows where >=80% of programs wrong:",int((wrongfrac>=.8).sum()),"label split",collections.Counter(y[wrongfrac>=.8].tolist()))
print("rows where >=60% wrong:",int((wrongfrac>=.6).sum()))

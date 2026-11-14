"""Committee-level and cross-program analysis for programs_synth_v3 (run deep_v3.py first)."""
import numpy as np, json, collections, re, random, pipeline as P
SP="analysis_programs/out_v3/"
te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); y=P.labels_of(te)
pred=np.load(SP+"pred_test.npy"); rows=json.load(open(SP+"deep_rows.json"))
ev=json.load(open("outputs/paper_baseline_synth_v3/evaluation_metrics.json"))
sel=ev["fit_summary"]["selected_program_ids"]; ids=[r["id"] for r in rows]; sc=[ids.index(i) for i in sel]
C=[json.loads(l) for l in open("outputs/paper_baseline_synth_v3/predictions_test.jsonl")]
cp=np.array([r["pred"] for r in C]); assert [r["id"] for r in C]==[r["id"] for r in te]
rc=np.array([r["relation_code"] for r in te]); tier=np.array([r["tier"] for r in te])
w=cp!=y
print(f"COMMITTEE (k={len(sel)}): acc {(~w).mean():.4f}; errors {w.sum()}: false yes {(w&(cp==1)).sum()}, false no {(w&(cp==0)).sum()}")
print(" by tier:",{t:round(float((cp[tier==t]==y[tier==t]).mean()),3) for t in ("easy","medium","edge","hard")})
err=collections.Counter(rc[w]); tot=collections.Counter(rc)
print(" errors by pair type (count, accuracy):",[(k,v,round(1-v/tot[k],2)) for k,v in err.most_common(10)])
# unanimity among selected
S=pred[:,sc]; agree_all=(S==S[:,[0]]).all(1)
print(f" committee errors where all {len(sel)} programs agree (no voting fix possible): {(w&agree_all).sum()} of {w.sum()} ({(w&agree_all).sum()/w.sum():.0%})")
nwrong=(S!=y[:,None]).sum(1)
print(" errors where >=9 of 11 wrong:",int((w&(nwrong>=9)).sum()))
# pairwise agreement among programs (independence assumption)
valid=[i for i,r in enumerate(rows) if r["uniq"]>1]
A=pred[:,valid]; agr=[(A[:,i]==A[:,j]).mean() for i in range(len(valid)) for j in range(i+1,len(valid))]
Asel=[(S[:,i]==S[:,j]).mean() for i in range(len(sel)) for j in range(i+1,len(sel))]
print(f"\nPAIRWISE AGREEMENT between programs: all 78 mean {np.mean(agr):.2f}; selected 11 mean {np.mean(Asel):.2f}")
# error correlation: when two programs are both wrong
E=(A!=y[:,None]); ew=[(E[:,i]&E[:,j]).sum()/max(1,(E[:,i]|E[:,j]).sum()) for i in range(len(valid)) for j in range(i+1,len(valid))]
print(f"error overlap (Jaccard of wrong-row sets) mean {np.mean(ew):.2f}")
# rubric of selected
man={e["program_id"]:e["heuristic_name"] for e in json.load(open("programs_synth_v3/manifest.json"))}
print("selected:",[(i,man[i]) for i in sel])
# by rubric mean acc
by=collections.defaultdict(list)
for r in rows:
    if r["uniq"]>1: by[man[r["id"]]].append(r["acc"])
print("rubric mean test acc:",sorted(((k,round(np.mean(v),3)) for k,v in by.items()),key=lambda x:-x[1]))
# examples
tok=lambda s:set(re.findall(r"[a-z]+",s.lower()))-{"g","raw","fresh","and","of","with","the","a","in","or"}
J=np.array([len(tok(r["ingredient"])&tok(r["usda_match"]))/max(1,len(tok(r["ingredient"])|tok(r["usda_match"]))) for r in te])
print(f"\ncommittee false no: mean word overlap {J[w&(cp==0)].mean():.2f}; false yes: {J[w&(cp==1)].mean():.2f}; correct yes {J[(~w)&(y==1)].mean():.2f}; correct no {J[(~w)&(y==0)].mean():.2f}")
rng=random.Random(1)
def show(mask,k):
    idx=list(np.where(mask)[0]); rng.shuffle(idx)
    for i in idx[:k]: print(f'   [{rc[i]}] truth={y[i]} {nwrong[i]}/11 wrong  "{te[i]["ingredient"]}" -> "{te[i]["usda_match"]}"')
print("committee FALSE NO, all 11 agree:"); show(w&(cp==0)&agree_all,10)
print("committee FALSE YES, all 11 agree:"); show(w&(cp==1)&agree_all,8)
print("committee errors with split vote:"); show(w&~agree_all,6)

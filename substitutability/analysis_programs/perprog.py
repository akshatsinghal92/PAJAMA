import numpy as np, pipeline as P, json, warnings; warnings.filterwarnings("ignore")
progs=P.load_programs_from_dir("programs_synth_v2")
man={e["program_id"]:e for e in json.load(open("programs_synth_v2/manifest.json"))}
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); rl=P.load_jsonl("data_synth_v2/pajama/real_external.jsonl")
pipe=P.fit(val,progs)
yt,yr=P.labels_of(te),P.labels_of(rl)
nt=P.normalize(P.collect_scores(te,progs),pipe.norm_params); nr=P.normalize(P.collect_scores(rl,progs),pipe.norm_params)
out=[]
for c,p in enumerate(progs):
    th=pipe.best_thresholds[c]
    pt=(np.nan_to_num(nt[:,c],nan=0.5)>=th).astype(int); pr=(np.nan_to_num(nr[:,c],nan=0.5)>=th).astype(int)
    m=man[p.program_id]
    out.append(dict(id=p.program_id,rub=m["heuristic_name"],v=m["variant"],th=round(float(th),2),val=round(float(pipe.best_accuracies[c]),3),
      t=round(float((pt==yt).mean()),3),fp=int(((pt==1)&(yt==0)).sum()),fn=int(((pt==0)&(yt==1)).sum()),yes=round(float(pt.mean()),2),
      r=round(float((pr==yr).mean()),3),rfp=int(((pr==1)&(yr==0)).sum()),rfn=int(((pr==0)&(yr==1)).sum()),
      ap=m.get("approach_summary","")[:110]))
json.dump(out,open("analysis_programs/out/perprog.json","w"))
s=sorted(out,key=lambda d:d["t"])
print("test acc dist: min",s[0]["t"],"median",s[40]["t"],"max",s[-1]["t"],"; majority 0.531; n<=0.531:",sum(d['t']<=0.531 for d in out))
for name,L in (("WORST",s[:10]),("BEST",s[::-1][:10])):
    print(name)
    for d in L: print(d)
import collections
by=collections.defaultdict(list)
for d in out: by[d["rub"]].append(d["t"])
print({k:round(sum(v)/len(v),3) for k,v in by.items()})
print("corr val vs test",np.corrcoef([d["val"] for d in out],[d["t"] for d in out])[0,1])

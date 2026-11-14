import json, numpy as np, collections, pipeline as P, warnings; warnings.filterwarnings("ignore")
rows=json.load(open("analysis_programs/out_v4/deep_rows.json"))
man={e["program_id"]:e for e in json.load(open("programs_synth_v4/manifest.json"))}
pred=np.load("analysis_programs/out_v4/pred_test.npy"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); y=P.labels_of(te)
by=collections.defaultdict(list)
for r in rows: by[man[r["id"]]["heuristic_id"]].append(r)
print("rubric mean acc / best / mean corr overlap / mean corr label")
for h in sorted(by): v=by[h]; print(h, man[v[0]["id"]]["heuristic_name"][:34].ljust(34), round(np.mean([x["acc"] for x in v]),3), max(x["acc"] for x in v), round(np.nanmean([x["rJ"] for x in v]),2), round(np.nanmean([x["rY"] for x in v]),2))
sel=[76,17,6,52,65,29]; print("selected:",[(i,man[i]["heuristic_name"],[r["acc"] for r in rows if r["id"]==i][0]) for i in sel])
A=(pred[:,:,None]==pred[:,None,:]).mean(0); n=A.shape[0]; print("mean pairwise agreement all",round(A[~np.eye(n,dtype=bool)].mean(),3))
idx=[ [r["id"] for r in rows].index(i) for i in sel]; As=A[np.ix_(idx,idx)]; print("selected",round(As[~np.eye(len(idx),dtype=bool)].mean(),3))
ens=[json.loads(l) for l in open("outputs/paper_baseline_synth_v4/predictions_test.jsonl")]
print(ens[0].keys())

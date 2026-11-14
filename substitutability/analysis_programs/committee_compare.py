import json, collections, numpy as np
print("Committee error breakdown on the generated test set (3,799 rows)")
data={}
for v in ("v3","v4","v5","v6"):
    e=[json.loads(l) for l in open(f"outputs/paper_baseline_synth_{v}/predictions_test.jsonl")]
    err=[r for r in e if r["pred"]!=r["label"]]
    t=collections.defaultdict(list); rc=collections.defaultdict(list)
    for r in e: t[r["tier"]].append(r["pred"]==r["label"]); rc[r["relation_code"]].append(r["pred"]==r["label"])
    data[v]=(e,err,t,rc)
    print(f"{v}: accuracy {np.mean([r['pred']==r['label'] for r in e]):.4f} errors {len(err)} false-yes {sum(r['pred']==1 for r in err)} false-no {sum(r['pred']==0 for r in err)}")
print("\nTier accuracy"); 
for tier in ("easy","medium","edge","hard"): print(tier.ljust(7)," ".join(f"{v}:{np.mean(data[v][2][tier]):.3f}" for v in data), "n=",len(data['v3'][2][tier]))
codes=sorted(data["v6"][3],key=lambda c:-sum(not x for x in data["v3"][3][c]))
print("\nPair type: accuracy (errors) per version, sorted by v3 errors")
for c in codes[:14]: print(c.ljust(4)," ".join(f"{v}:{np.mean(data[v][3][c]):.2f}({sum(not x for x in data[v][3][c])})" for v in data),"n=",len(data['v3'][3][c]))
# overlap of error sets between versions' committees
E={v:{r["id"] for r in data[v][1]} for v in data}
print("\nRows wrong for the committee of all four versions:",len(set.intersection(*E.values())),"; v6 errors also made by v4:",len(E['v6']&E['v4']),"of",len(E['v6']))

import numpy as np, json, collections, pipeline as P
SP="analysis_programs/out/"
rows=json.load(open(SP+"deep_rows.json")); S=np.load(SP+"S_test.npy"); pred=np.load(SP+"pred_test.npy"); wf=np.load(SP+"wrongfrac.npy")
te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); y=P.labels_of(te)
print("id rubric                  uniq mode yes  acc  rJ   rY")
for r in sorted(rows,key=lambda r:r["acc"]): print(f'{r["id"]:2d} {r["rub"]:22s} {r["uniq"]:4d} {r["mode"]:.2f} {r["yes"]:.2f} {r["acc"]:.3f} {r["rJ"]:.2f} {r["rY"]:.2f}')
flat=[i for i,r in enumerate(rows) if r["mode"]>=.5]
print("\nFLAT programs: the most common score, and accuracy on those rows vs the rest")
for c in flat:
    s=np.round(S[:,c],4); v,cnt=collections.Counter(s).most_common(1)[0]; m=s==v
    print(f' id{rows[c]["id"]:2d} default={v} on {m.mean():.0%} rows -> all predicted {int(pred[m,c].mean().round())}; acc on default rows {(pred[m,c]==y[m]).mean():.2f}, on others {(pred[~m,c]==y[~m]).mean():.2f}')
print("\nROWS that >=80% of programs get wrong (sample):")
idx=np.where(wf>=.8)[0]; rng=np.random.RandomState(0); rng.shuffle(idx)
for i in idx[:22]: r=te[i]; print(f'  {wf[i]:.2f} [{r["relation_code"]}] truth={r["label"]} "{r["ingredient"]}" -> "{r["usda_match"]}"')

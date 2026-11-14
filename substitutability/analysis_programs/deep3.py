import numpy as np, json, re, collections, pipeline as P, glob
SP="analysis_programs/out/"
rows=json.load(open(SP+"deep_rows.json")); S=np.load(SP+"S_test.npy"); pred=np.load(SP+"pred_test.npy")
te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); y=P.labels_of(te); rc=np.array([r["relation_code"] for r in te])
# 1. code patterns
codes={int(re.findall(r"\d+",f)[-1]):open(f).read() for f in glob.glob("programs_synth_v2/judge_*.py")}
pat={"starts at max score and subtracts (veto style)":r"score\s*=\s*(10(\.0)?|100(\.0)?|1(\.0)?)\s*\n",
     "drops text after first comma of ingredient":r"split\(\s*[\"'],[\"']\s*\)\s*\[\s*0\s*\]",
     "mentions 'sodium'":r"sodium","mentions synonyms/aliases table":r"(?i)synonym|alias",
     "uses a hand-written word list (dict/list of food words)":r"_[A-Z_]{3,}\s*=\s*[\[\{(]"}
for k,p in pat.items(): print(f"{k}: {sum(bool(re.search(p,c)) for c in codes.values())}/80")
veto=[i for i,c in codes.items() if re.search(pat["starts at max score and subtracts (veto style)"],c)]
idx={r["id"]:j for j,r in enumerate(rows)}
print("mean acc veto-style",np.mean([rows[idx[i]]["acc"] for i in veto]).round(3),"vs others",np.mean([r["acc"] for r in rows if r["id"] not in veto]).round(3))
print("mean yes-rate veto-style",np.mean([rows[idx[i]]["yes"] for i in veto]).round(2))
# 2. clearly different foods (B1,B2,B3): how many programs say yes?
for code in ("B1","B2","B3"):
    m=rc==code; print(f"{code} (different food) avg share of programs saying YES: {pred[m].mean():.2f}")
# 3. qualifier gap: USDA has health/fat/salt qualifier the ingredient lacks
Q=r"low sodium|reduced sodium|no salt|nonfat|non-fat|fat free|fat-free|low fat|lowfat|reduced fat|light|reduced sugar|sugar free|unsweetened|sweetened|with salt|low calorie|reduced calorie|diet"
gap=np.array([bool(re.search(Q,r["usda_match"].lower())) and not re.search(Q,r["ingredient"].lower()) for r in te])
print("rows where USDA adds a fat/salt/sugar qualifier the ingredient lacks:",gap.sum(),"| truth=no share",y[gap].mean().round(2)*-1+1)
print("  avg share of programs saying YES on those 'no' rows:",pred[gap&(y==0)].mean().round(2),"(n=%d)"%(gap&(y==0)).sum())
print("  programs that say NO on >=70% of those rows:",int(((1-pred[gap&(y==0)]).mean(0)>=.7).sum()),"/80")
# 4. synonym: truth yes, core word overlap zero
tok=lambda s:set(re.findall(r"[a-z]+",s.lower()))-{"g","raw","fresh","and","of","with","the","a","in","or"}
zero=np.array([len(tok(r["ingredient"])&tok(r["usda_match"]))==0 for r in te])
print("truth=yes rows with ZERO shared words:",(zero&(y==1)).sum(),"| avg share of programs saying YES:",pred[zero&(y==1)].mean().round(2))
print("truth=no rows with ZERO shared words:",(zero&(y==0)).sum(),"| avg share saying YES:",pred[zero&(y==0)].mean().round(2))

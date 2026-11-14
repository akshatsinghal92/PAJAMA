import numpy as np, re, pipeline as P
SP="analysis_programs/out_v3/"
pred=np.load(SP+"pred_test.npy"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); y=P.labels_of(te)
Q=r"low sodium|reduced sodium|nonfat|fat free|low fat|lowfat|reduced fat|unsweetened|sweetened|unsalted|salted|hulled|unhulled|skinless|boneless|reduced sugar|light|cooked|raw|dried|canned|frozen|toasted|untoasted"
tail=np.array([("," in r["ingredient"]) and bool(re.search(Q,r["ingredient"].split(",",1)[1].lower())) for r in te])
acc=(pred==y[:,None]).mean(1)
print("ingredient has a qualifier after its first comma:",tail.sum(),"rows; avg program accuracy",acc[tail].mean().round(3),"vs other rows",acc[~tail].mean().round(3))
for i in np.where(tail&(acc<.35))[0][:6]: print("  ",round(acc[i],2),te[i]["label"],te[i]["ingredient"],"->",te[i]["usda_match"])

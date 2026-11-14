import numpy as np, pipeline as P, json, warnings, difflib; warnings.filterwarnings("ignore")
import generate_programs as G
progs=P.load_programs_from_dir("programs_synth_v4"); man={e["program_id"]:e for e in json.load(open("programs_synth_v4/manifest.json"))}
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); te=P.load_jsonl("data_synth_v2/pajama_paper/test.jsonl"); yv=P.labels_of(val); yt=P.labels_of(te)
keep=[p for p in progs if man[p.program_id]["status"]=="success"]; ids=[p.program_id for p in keep]
code={p.program_id:open(f"programs_synth_v4/judge_{p.program_id}.py").read() for p in keep}
def errs(rows,y,ps):
    S=P.collect_scores(rows,ps); n=P.normalize(S,P.compute_norm_params(S)); n=np.nan_to_num(n,nan=.5)
    t,a=P.tune_thresholds(n,y); pred=(n>=t[None,:]).astype(int); return pred!=y[:,None],a   # own norm+threshold per program
Ev,acc=errs(val,yv,keep); Et,_=errs(te,yt,keep)   # test errors use test-fit norm only for the diagnostic below
# for test use val-fit params like the pipeline
S=P.collect_scores(val,keep); prm=P.compute_norm_params(S); t,_=P.tune_thresholds(np.nan_to_num(P.normalize(S,prm),nan=.5),yv)
St=P.collect_scores(te,keep); Et=((np.nan_to_num(P.normalize(St,prm),nan=.5)>=t[None,:]).astype(int)!=yt[:,None])
m=len(keep); CS=np.zeros((m,m))
for i in range(m):
    for j in range(i):
        CS[i,j]=CS[j,i]=G.difflib.SequenceMatcher(None,G.clean_for_similarity(code[ids[i]]),G.clean_for_similarity(code[ids[j]])).ratio()
def jac(E):
    I=(E[:,:,None]&E[:,None,:]).sum(0); U=(E[:,:,None]|E[:,None,:]).sum(0); return I/np.maximum(U,1)
JV=jac(Ev); JT=jac(Et); off=~np.eye(m,dtype=bool)
print("pairs:",m*(m-1)//2)
print("code similarity: mean %.3f p50 %.3f p90 %.3f max %.3f   pairs >0.60: %d"%(CS[off].mean(),np.median(CS[off]),np.percentile(CS[off],90),CS[off].max(),(CS[off]>.6).sum()//2))
print("val error-Jaccard: mean %.3f p50 %.3f p90 %.3f max %.3f"%(JV[off].mean(),np.median(JV[off]),np.percentile(JV[off],90),JV[off].max()))
print("test error-Jaccard: mean %.3f p50 %.3f p90 %.3f max %.3f"%(JT[off].mean(),np.median(JT[off]),np.percentile(JT[off],90),JT[off].max()))
print("corr(val err-Jaccard, test err-Jaccard) over pairs:",round(np.corrcoef(JV[off],JT[off])[0,1],3))
print("corr(code sim, test err-Jaccard):",round(np.corrcoef(CS[off],JT[off])[0,1],3),"  corr(code sim, val err-Jaccard):",round(np.corrcoef(CS[off],JV[off])[0,1],3))
# replay in slot order
for w in (0.0,0.3,0.5):
    print(f"\n-- combined = {w:.1f}*code_sim + {1-w:.1f}*val_err_jaccard (max over earlier programs); replay in slot order")
    comb=np.array([ (w*CS[i,:i]+(1-w)*JV[i,:i]).max() if i else 0 for i in range(m)])
    print(" distribution of per-program max combined: p50 %.3f p75 %.3f p90 %.3f max %.3f"%tuple(np.percentile(comb[1:],[50,75,90,100])))
    for tau in np.round(np.percentile(comb[1:],[95,90,80,70,60]),3):
        rej=[ids[i] for i in range(1,m) if comb[i]>tau]; print(f"   tau {tau:.3f}: would reject {len(rej)} of {m}: {rej[:20]}")
# real redundancy check: for the pairs flagged by val, is test agreement really high?
print("\nthe 10 pairs with highest val error-Jaccard: (ids, val J, test J, code sim)")
iu=np.argwhere(np.triu(JV,1)>0); top=sorted(iu,key=lambda ij:-JV[ij[0],ij[1]])[:10]
for i,j in top: print(ids[i],ids[j],round(JV[i,j],2),round(JT[i,j],2),round(CS[i,j],2))
print("val accuracy of programs: min %.3f median %.3f"%(acc.min(),np.median(acc)))
np.save("analysis_programs/out_v4/replay_CS.npy",CS); np.save("analysis_programs/out_v4/replay_JV.npy",JV); np.save("analysis_programs/out_v4/replay_JT.npy",JT)

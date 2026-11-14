import numpy as np, pipeline as P, warnings; warnings.filterwarnings("ignore")
progs=P.load_programs_from_dir("programs_synth_v2")
val=P.load_jsonl("data_synth_v2/pajama_paper/val.jsonl"); fs=P.load_jsonl("data_synth_v2/pajama_paper/fewshot.jsonl")
pipe=P.fit(val,progs); yf=P.labels_of(fs); yv=P.labels_of(val)
nf=P.normalize(P.collect_scores(fs,progs),pipe.norm_params)
print("fewshot n",len(fs),"yes",int(yf.sum()))
M=P.build_label_matrix(nf,pipe.selected_cols,pipe.best_thresholds,0.0)
h=pipe.label_model.predict(L=M,tie_break_policy="random"); h=np.where(h==-1,0,h)
print("committee k=3 on few-shot:",(h==yf).mean(),"| on full val (380):",round(float((np.where(pipe.label_model.predict(L=P.build_label_matrix(P.normalize(P.collect_scores(val,progs),pipe.norm_params),pipe.selected_cols,pipe.best_thresholds,0.0),tie_break_policy='random')==-1,0,pipe.label_model.predict(L=P.build_label_matrix(P.normalize(P.collect_scores(val,progs),pipe.norm_params),pipe.selected_cols,pipe.best_thresholds,0.0),tie_break_policy='random'))==yv).mean()),3))
acc=[]
for c in range(len(progs)):
    p=(np.nan_to_num(nf[:,c],nan=.5)>=pipe.best_thresholds[c]).astype(int); acc.append((p==yf).mean())
acc=np.array(acc); print("per-program few-shot acc: mean",acc.mean().round(3),"median",np.median(acc),"min",acc.min(),"max",acc.max())
print("val-acc mean over programs",pipe.best_accuracies.mean().round(3))
print("programs >=0.9 on fewshot:",(acc>=.9).sum(),"; ==1.0:",(acc==1).sum(),"; <=0.5:",(acc<=.5).sum())
# majority vote of all 80 / all 78 survivors, and top-k sweep on fewshot
ranked=[int(i) for i in np.argsort(pipe.best_accuracies)[::-1] if pipe.best_accuracies[i]>=.5]
for k in (3,10,20,len(ranked)):
    Mk=P.build_label_matrix(nf,ranked[:k],pipe.best_thresholds,0.0)
    v=np.where(Mk==-1,np.nan,Mk).astype(float);pp=np.nanmean(v,1);hh=(pp>.5).astype(int)
    print(f"majority vote top-{k}:",(hh==yf).mean())
for r,p,y in zip(fs,h,yf): print(y,int(p),r["ingredient"],"->",r["usda_match"])

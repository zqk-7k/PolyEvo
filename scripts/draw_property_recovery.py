"""Reproduce supplementary property recovery from preserved observations."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
parser=argparse.ArgumentParser()
parser.add_argument('--data',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
D=args.data/'figures/figureS1';O=args.output;O.mkdir(parents=True,exist_ok=True)
pairs=pd.read_csv(D/'pairs.csv')
obs=pd.DataFrame(json.loads((D/'property_groups.json').read_text(encoding='utf-8')))
families=list(json.loads((D/'family_mapping.json').read_text(encoding='utf-8')))
P='#4E5055';G='#A65B4B';C='#A65B4B';N='#9B9691';GRID='#EBE8E5';BLACK='#171717'
RECALL=LinearSegmentedColormap.from_list('recall',['#FBF9F6','#DEC2B8','#A65B4B'])
def style(kind='science'):
    mpl.rcParams.update({'font.family':'Arial','font.size':8,'axes.titlesize':9,
      'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,
      'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,
      'pdf.fonttype':42,'svg.fonttype':'none','text.usetex':False,
      'savefig.facecolor':'white','figure.facecolor':'white'})

def figure(h=155,kind='science'):
    style(kind)
    return plt.figure(figsize=(180/25.4,h/25.4))

def label(fig,x,y,letter,title):
    fig.text(x,y,letter,fontsize=11,fontweight='bold',va='top')
    fig.text(x+.028,y,title,fontsize=9,fontweight='bold',va='top')

def clean(ax,grid='y'):
    ax.grid(axis=grid,color=GRID,lw=.5,zorder=0); ax.set_axisbelow(True)

def prop_tables():
    refs=sorted(pairs[pairs.cohort==31].reference_no)
    b=obs.assign(hit=obs.before.eq('final')).groupby(['reference_no','family']).hit.agg(['sum','count'])
    a=obs.assign(hit=obs.after.eq('final')).groupby(['reference_no','family']).hit.agg(['sum','count'])
    gain=(100*(a['sum']-b['sum'])/a['count']).unstack().reindex(index=refs,columns=families)
    den=a['count'].unstack().reindex(index=refs,columns=families)
    final=(100*a['sum']/a['count']).unstack().reindex(index=refs,columns=families)
    pooled=pd.DataFrame({k:{'D':len(g),'before':g.before.eq('final').sum(),'after':g.after.eq('final').sum(),'upstream':g.after.eq('upstream_only').sum(),'absent':g.after.eq('absent').sum()} for k,g in obs.groupby('family')}).T.reindex(families)
    assert pooled.D.sum()==1381
    (O/'property_pooled.json').write_text(pooled.reset_index(names='family').to_json(orient='records',indent=2),encoding='utf8')
    (O/'property_matrices.json').write_text(json.dumps({'refs':refs,'families':families,'gain':gain.replace({np.nan:None}).values.tolist(),'D':den.replace({np.nan:None}).values.tolist(),'final':final.replace({np.nan:None}).values.tolist()},indent=2),encoding='utf8')
    return refs,gain,den,final,pooled

def property_b():
    refs,gain,den,final,pool=prop_tables();f=figure(160,'cns')
    label(f,.025,.98,'a','Final numerical recovery across property families')
    ax=f.add_axes([.085,.19,.53,.71]);xs=[];ys=[];ss=[];cs=[]
    for y in range(len(refs)):
        for x in range(len(families)):
            d=den.iloc[y,x]
            if pd.notna(d):xs.append(x);ys.append(y);ss.append(10+1.9*d);cs.append(final.iloc[y,x])
    im=ax.scatter(xs,ys,s=ss,c=cs,cmap=RECALL,vmin=0,vmax=100,edgecolors='#574A46',linewidths=.25)
    ax.set(xticks=range(9),xticklabels=families,yticks=range(31),yticklabels=[f'{i+1:02}' for i in range(31)],ylim=(30.7,-.7),xlim=(-.7,8.7),ylabel='Initial-cohort paper index')
    plt.setp(ax.get_xticklabels(),rotation=40,ha='right',rotation_mode='anchor');ax.tick_params(length=0);ax.spines[['left','bottom']].set_visible(False);ax.grid(color=GRID,lw=.4);ax.set_axisbelow(True)
    ca=f.add_axes([.12,.072,.29,.016]);f.colorbar(im,cax=ca,orientation='horizontal',label='Final numerical recall (%)')
    label(f,.67,.98,'b','Reference composition')
    ax=f.add_axes([.78,.605,.17,.29]);ax.barh(range(9),pool.D,color=N);ax.set(yticks=range(9),yticklabels=families,ylim=(8.7,-.7),xlabel='Reference groups');ax.tick_params(axis='y',length=0);clean(ax,'x')
    for i,v in enumerate(pool.D):ax.text(v+8,i,str(v),va='center',fontsize=7)
    ax.set_xlim(0,max(pool.D)*1.27)
    label(f,.67,.47,'c','Recovered final groups')
    ax=f.add_axes([.78,.19,.17,.21]);g=pool.after-pool.before
    ax.barh(range(9),g,color=C);ax.set(yticks=range(9),yticklabels=families,ylim=(8.7,-.7),xlabel='Net additional groups');ax.tick_params(axis='y',length=0);clean(ax,'x')
    f.text(.67,.06,'Circle area = 10 + 1.9 × group count\nBlank = no eligible reference groups',size=6.5,linespacing=1.6)
    finish(f,'Properties_B_bubble','性质 B｜气泡矩阵＋组成分布','cnsplots + Matplotlib','气泡颜色表示最终Recall、面积随参考数量变化，右侧显示参考组成及新增最终匹配数量。')
def finish(fig,name,*unused):
    fig.savefig(O/'Figure_S1.pdf')
    fig.savefig(O/'Figure_S1.svg')
    fig.savefig(O/'Figure_S1.png',dpi=300)
    plt.close(fig)
if __name__=='__main__':property_b()

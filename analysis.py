import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.stats import t as student_t

MODELS = {'PFO': lambda t,a,k:a*np.exp(-k*t), 'Second-order':lambda t,a,k:a/(1+a*k*t), 'Zero-order':lambda t,a,k:a-k*t}

def validate(d):
    d=d.copy()
    for c in ['time','pollutant']:
        d[c]=pd.to_numeric(d[c],errors='raise')
    if 'oxidant' in d: d['oxidant']=pd.to_numeric(d['oxidant'],errors='raise')
    if d[['condition','replicate','time','pollutant']].isna().any().any(): raise ValueError('필수 열에 결측값이 있습니다.')
    if not np.isfinite(d[['time','pollutant']].to_numpy()).all(): raise ValueError('무한대 값은 사용할 수 없습니다.')
    if (d[['time','pollutant']]<0).any().any(): raise ValueError('음수 시간/농도는 사용할 수 없습니다.')
    if 'oxidant' in d and ((d.oxidant.dropna()<0).any() or np.isinf(d.oxidant).any()): raise ValueError('산화제 농도를 확인하세요.')
    d['condition']=d.condition.astype(str);d['replicate']=d.replicate.astype(str)
    if d.duplicated(['condition','replicate','time']).any(): raise ValueError('condition/replicate/time 중복: 반복측정에 다른 replicate ID를 지정하세요.')
    return d.sort_values(['condition','replicate','time'])

def baseline(d,col):
    rows=[]
    for _,g in d.groupby(['condition','replicate'],sort=False):
        g=g.copy(); b=g.loc[g.time==0,col]
        if len(b)!=1 or pd.isna(b.iloc[0]) or b.iloc[0]<=0: raise ValueError(f'{g.condition.iloc[0]}/{g.replicate.iloc[0]}: {col}의 양수 t=0 값이 필요합니다.')
        g['normalized']=g[col]/b.iloc[0];g['delta']=b.iloc[0]-g[col];rows.append(g)
    return pd.concat(rows)

def fit(x,y,model='PFO',fixed=False):
    x=np.asarray(x,float);y=np.asarray(y,float); mask=np.isfinite(x)&np.isfinite(y);x=x[mask];y=y[mask]
    p=1 if fixed else 2
    if len(x)<=p or len(np.unique(x))<=p: raise ValueError('피팅에 충분한 서로 다른 시간점이 필요합니다.')
    if fixed:
        f=lambda x,k:MODELS[model](x,1.,k); init=[.01]
    else:
        f=MODELS[model];init=[max(y[0],1e-8),.01]
    pars,cov=curve_fit(f,x,y,p0=init,bounds=(0,np.inf),maxfev=30000)
    if not np.isfinite(cov).all(): raise ValueError('파라미터 불확실성을 추정할 수 없습니다.')
    k=pars[-1];se=np.sqrt(cov[-1,-1]);df=len(x)-p;ci=student_t.ppf(.975,df)*se;pred=f(x,*pars)
    ss=np.sum((y-y.mean())**2)
    return dict(k=k,SE=se,CI_low=k-ci,CI_high=k+ci,R2=1-np.sum((y-pred)**2)/ss if ss>0 else np.nan,n=len(x),df=df,A=1. if fixed else pars[0]),pred

def regression(x,y,kind='Linear',origin=False):
    x=np.asarray(x,float);y=np.asarray(y,float);m=np.isfinite(x)&np.isfinite(y);x=x[m];y=y[m]
    degree=2 if kind=='Quadratic' else 1
    X=np.column_stack([x**i for i in range(0 if not origin else 1,degree+1)])
    if len(x)<=X.shape[1] or np.linalg.matrix_rank(X)<X.shape[1]: raise ValueError('회귀에 충분한 독립 x값이 필요합니다.')
    beta=np.linalg.lstsq(X,y,rcond=None)[0];pred=X@beta;df=len(x)-len(beta);sse=np.sum((y-pred)**2);cov=sse/df*np.linalg.inv(X.T@X);se=np.sqrt(np.diag(cov));ci=student_t.ppf(.975,df)*se
    powers=list(range(1 if origin else 0,degree+1));table=pd.DataFrame({'term':[f'x^{i}' for i in powers],'estimate':beta,'SE':se,'CI_low':beta-ci,'CI_high':beta+ci})
    ss=np.sum((y if origin else y-y.mean())**2)
    return table,lambda xx:sum(b*np.asarray(xx)**i for b,i in zip(beta,powers)),1-sse/ss if ss>0 else np.nan

def demo():
    rng=np.random.default_rng(42);rows=[]
    for rpm,k in [(0,.012),(50,.027),(100,.043),(200,.071)]:
        for r in range(1,4):
            a=10*rng.uniform(.96,1.04);o=rng.uniform(.96,1.04)
            for tm in [0,5,10,20,30,45,60]:
                rows.append([f'{rpm} rpm',r,tm,a if tm==0 else max(0,a*np.exp(-k*tm)+rng.normal(0,.12)),o if tm==0 else o*np.exp(-.008*tm),rpm])
    return pd.DataFrame(rows,columns=['condition','replicate','time','pollutant','oxidant','rpm'])

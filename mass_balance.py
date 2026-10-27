"""Soil / aqueous contaminant inventories (dry-soil basis)."""
import numpy as np
import pandas as pd

KEYS=['condition','replicate','time']

def inventory(data, soil_g=10., water_ml=100., geometry=None):
    """Convert soil mg/kg and water mg/L into phase and total mg.

    geometry: optional DataFrame with condition, soil_g, water_ml, allowing
    condition-specific geometry. Each replicate/time shares its condition geometry.
    """
    d=data.copy()
    for c in KEYS+['soil','aqueous']:
        if c not in d: raise ValueError(f'필수 열 누락: {c}')
    for c in ['time','soil','aqueous']:
        d[c]=pd.to_numeric(d[c],errors='raise')
    if d[KEYS+['soil','aqueous']].isna().any().any():
        raise ValueError('시간·토양·수용액 입력에 결측값이 있습니다.')
    if not np.isfinite(d[['time','soil','aqueous']].to_numpy()).all() or (d[['time','soil','aqueous']]<0).any().any():
        raise ValueError('음수 또는 무한대 농도/시간은 사용할 수 없습니다.')
    d['condition']=d.condition.astype(str);d['replicate']=d.replicate.astype(str)
    if d.duplicated(KEYS).any():raise ValueError('condition/replicate/time 중복 관측값이 있습니다.')
    if geometry is None:
        d['soil_g']=soil_g;d['water_ml']=water_ml
    else:
        g=geometry.copy();g['condition']=g.condition.astype(str)
        if g.condition.duplicated().any():raise ValueError('조건별 반응기 정보가 중복되었습니다.')
        d=d.merge(g[['condition','soil_g','water_ml']],on='condition',how='left',validate='many_to_one')
    for c in ['soil_g','water_ml']:
        d[c]=pd.to_numeric(d[c],errors='coerce')
        if d[c].isna().any() or (~np.isfinite(d[c])).any() or (d[c]<=0).any():raise ValueError(c+'은 유한한 양수여야 합니다.')
    d['soil_mass']=d.soil*d.soil_g/1000.
    d['aqueous_mass']=d.aqueous*d.water_ml/1000.
    d['total_mass']=d.soil_mass+d.aqueous_mass
    init=d.loc[d.time==0,KEYS[:2]+['soil_mass','aqueous_mass','total_mass']].copy()
    if init.duplicated(KEYS[:2]).any():raise ValueError('각 반복실험에 t=0 데이터는 한 개여야 합니다.')
    init=init.rename(columns={c:c+'_initial' for c in ['soil_mass','aqueous_mass','total_mass']})
    d=d.merge(init,on=KEYS[:2],how='left',validate='many_to_one')
    if d.total_mass_initial.isna().any() or (d.total_mass_initial<=0).any():
        raise ValueError('각 조건/반복실험에 양수인 전체 초기 오염물질량(t=0)이 필요합니다.')
    for phase in ['soil','aqueous','total']:
        m='total_mass' if phase=='total' else phase+'_mass'
        d[phase+'_fraction_of_initial_total']=d[m]/d.total_mass_initial
        initial=m+'_initial'
        d[phase+'_fraction_of_own_initial']=np.where(d[initial]>0,d[m]/d[initial],np.nan)
    d['removed_mass']=d.total_mass_initial-d.total_mass
    d['removed_fraction']=d.removed_mass/d.total_mass_initial
    return d.sort_values(KEYS).reset_index(drop=True)

def molar_removed(d,mw):
    if not np.isfinite(mw) or mw<=0:raise ValueError('오염물질 분자량은 양수여야 합니다.')
    return d.removed_mass.to_numpy()/1000./mw

def oxidant_consumed_mol(d,unit='mM',mw=152.17):
    """Measured aqueous-phase oxidant loss. Water volume is in mL."""
    if 'oxidant' not in d:raise ValueError('산화제 농도 열이 없습니다.')
    x=d.copy();x['oxidant']=pd.to_numeric(x.oxidant,errors='coerce')
    initial=x[x.time==0][KEYS[:2]+['oxidant']].rename(columns={'oxidant':'oxidant_initial'})
    if initial.duplicated(KEYS[:2]).any():raise ValueError('산화제 t=0 중복.')
    x=x.merge(initial,on=KEYS[:2],how='left',validate='many_to_one')
    factor={'mM':1e-3,'µM':1e-6,'mol/L':1,'mg/L':1e-3/mw,'µg/L':1e-6/mw}
    if unit not in factor:raise ValueError('지원하지 않는 산화제 단위')
    if mw<=0:raise ValueError('산화제 분자량은 양수여야 합니다.')
    x['oxidant_consumed_mol']=(x.oxidant_initial-x.oxidant)*factor[unit]*x.water_ml/1000.
    return x

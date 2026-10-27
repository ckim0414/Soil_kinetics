import numpy as np
import pandas as pd
import pytest
from mass_balance import inventory, oxidant_consumed_mol

def test_partial_phase_and_mismatched_replicate_timepoints():
    d=pd.DataFrame([
        ['A',1,0,100,0.2,10],
        ['A',1,1,80,np.nan,8],
        ['A',1,2,np.nan,0.3,np.nan],
        ['A',2,0,90,0.1,10],
        ['A',2,2,60,0.2,7],
        ['A',2,4,np.nan,np.nan,np.nan],
    ],columns=['condition','replicate','time','soil','aqueous','oxidant'])
    x=inventory(d)
    assert len(x)==5
    assert x.loc[(x.replicate=='1')&(x.time==1),'soil_mass'].iloc[0]==pytest.approx(0.8)
    assert np.isnan(x.loc[(x.replicate=='1')&(x.time==1),'total_mass'].iloc[0])
    assert np.isnan(x.loc[(x.replicate=='1')&(x.time==2),'removed_mass'].iloc[0])
    assert x.loc[(x.replicate=='2')&(x.time==2),'total_mass'].iloc[0]==pytest.approx(.62)
    assert np.isnan(oxidant_consumed_mol(x).loc[(x.replicate=='1')&(x.time==2),'oxidant_consumed_mol'].iloc[0])

def test_missing_initial_allows_raw_data():
    d=pd.DataFrame({'condition':['A','A','B','B'],'replicate':[1,1,2,2],'time':[0,1,1,2],'soil':[100,80,90,70],'aqueous':[np.nan,1.,2.,1.]})
    x=inventory(d)
    assert np.isnan(x.loc[x.condition=='A','total_mass_initial']).all()
    assert np.isnan(x.loc[x.condition=='B','total_mass_initial']).all()
    assert x.soil_mass.notna().all()

def test_required_keys_and_invalid_negative_still_block():
    d=pd.DataFrame({'condition':['A'],'replicate':[1],'time':[0],'soil':[-2],'aqueous':[np.nan]})
    with pytest.raises(ValueError): inventory(d)
    d.loc[0,'soil']=2; d.loc[0,'time']=np.nan
    with pytest.raises(ValueError): inventory(d)

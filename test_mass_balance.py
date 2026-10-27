import numpy as np
import pandas as pd
import pytest
from mass_balance import inventory,oxidant_consumed_mol

def test_inventory_and_zero_water():
    d=pd.DataFrame({'condition':['A']*3,'replicate':[1]*3,'time':[0,1,2], 'soil':[100,80,60],'aqueous':[0,1,0.5],'oxidant':[10,8,7]})
    out=inventory(d,soil_g=10,water_ml=100)
    assert np.allclose(out.total_mass,[1,0.9,0.65])
    assert np.allclose(out.removed_mass,[0,.1,.35])
    assert np.isnan(out.aqueous_fraction_of_own_initial.iloc[0])
    assert out.aqueous_fraction_of_initial_total.iloc[1]==pytest.approx(.1)
    ox=oxidant_consumed_mol(out,unit='mM')
    assert ox.oxidant_consumed_mol.iloc[1]==pytest.approx(.0002)

def test_geometry_and_duplicates():
    d=pd.DataFrame({'condition':['A','B'],'replicate':[1,1],'time':[0,0],'soil':[100,100],'aqueous':[1,1]})
    geom=pd.DataFrame({'condition':['A','B'],'soil_g':[10,20],'water_ml':[100,200]})
    out=inventory(d,geometry=geom)
    assert out.total_mass.tolist()==pytest.approx([1.1,2.2])
    with pytest.raises(ValueError):inventory(pd.concat([d,d.iloc[:1]]),geometry=geom)

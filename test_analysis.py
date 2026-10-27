import unittest
import numpy as np
from analysis import fit,regression,validate,baseline,demo
class Tests(unittest.TestCase):
    def test_recovery(self):
        x=np.array([0,5,10,20,30,60]);r,_=fit(x,10*np.exp(-.04*x));self.assertAlmostEqual(r['k'],.04,places=7)
        r,_=fit(x,np.exp(-.04*x),fixed=True);self.assertAlmostEqual(r['k'],.04,places=7)
    def test_regression(self):
        x=np.arange(6);table,fn,r2=regression(x,2+3*x);self.assertAlmostEqual(table.estimate.iloc[1],3);self.assertAlmostEqual(r2,1)
    def test_pairing(self):
        d=validate(demo());b=baseline(d,'pollutant');self.assertTrue((b.loc[b.time==0,'delta']==0).all())
        with self.assertRaises(ValueError):validate(__import__('pandas').concat([d,d.iloc[:1]]))
        with self.assertRaises(ValueError):baseline(d[d.time!=0],'pollutant')
if __name__=='__main__':unittest.main()

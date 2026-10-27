import unittest
from streamlit.testing.v1 import AppTest
class UITests(unittest.TestCase):
    def app(self):return AppTest.from_file('app.py',default_timeout=90)
    def check(self,a):
        self.assertFalse(a.exception,[e.message for e in a.exception]);self.assertFalse(a.error,[e.value for e in a.error])
    def test_modes(self):
        a=self.app().run();self.check(a)
        a.selectbox(key='o_model').select('PFO');a.selectbox(key='effect_pollutant_kind').select('Linear');a.run();self.check(a)
        a.selectbox(key='o_strategy').select('각 반복실험 별도 피팅');a.checkbox(key='util_molar').check();a.checkbox(key='plot_Pollutant kinetics_legend').uncheck();a.text_input(key='plot_Oxidant kinetics_xlabel').input('Persulfate ($S_2O_8^{2-}$)');a.run();self.check(a)
        a.selectbox(key='global_palette').select('Deep muted');a.selectbox(key='effect_oxidant_kind').select('Quadratic');a.run();self.check(a)
        a.selectbox(key='o_model').select('None');a.run();self.check(a)
        a.selectbox(key='p_model').select('None');a.run();self.check(a)
    def test_restored_state(self):
        a=self.app();a.session_state['global_palette']='Deep muted';a.session_state['o_model']='PFO';a.session_state['plot_Pollutant kinetics_legend']=False
        a.session_state['_restored_styles']=[{'condition':'0 rpm','x':0.,'label':'Control','color':'#123456','marker':'□ 사각형','fill':'Filled'}]
        a.session_state['_restored_palette']='Deep muted';a.run();self.check(a)
        self.assertEqual(a.selectbox(key='o_model').value,'PFO');self.assertFalse(a.checkbox(key='plot_Pollutant kinetics_legend').value)
        a.run();self.check(a)
if __name__=='__main__':unittest.main()

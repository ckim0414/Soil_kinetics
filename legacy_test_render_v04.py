import unittest
from unittest.mock import patch
from matplotlib.figure import Figure
from streamlit.testing.v1 import AppTest
class RenderTests(unittest.TestCase):
    def test_actual_figures(self):
        captured=[];original=Figure.savefig
        def capture(fig,*args,**kwargs):
            for ax in fig.axes:
                if ax.get_ylabel()=='Custom concentration':
                    captured.append((ax.get_ylabel(),ax.xaxis.get_majorticklocs().copy(),ax.yaxis.label.get_fontfamily()))
            return original(fig,*args,**kwargs)
        a=AppTest.from_file('app.py',default_timeout=90).run()
        a.text_input(key='plot_Pollutant kinetics_ylabel').input('Custom concentration')
        a.text_input(key='plot_Pollutant kinetics_xtick').input('7')
        a.selectbox(key='global_font').select('DejaVu Serif')
        with patch.object(Figure,'savefig',capture):a.run()
        self.assertFalse(a.exception);self.assertFalse(a.error)
        self.assertTrue(captured)
        for label,locs,font in captured:
            self.assertTrue(all(abs((locs[i+1]-locs[i])-7)<1e-9 for i in range(len(locs)-1)))
            self.assertEqual(font,['DejaVu Serif'])
if __name__=='__main__':unittest.main()

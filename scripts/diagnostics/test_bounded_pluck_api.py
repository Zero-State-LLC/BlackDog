import sys, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'shipwright-integration'))
from shipwright import engine,config
from shipwright.registry import Track,Note,RenderSpec
from bounded_pluck_instrument import bounded_pluck,preflight
SOURCE=(ROOT/'pluck-bounded-epoch.dsp').read_text()
class Contract(unittest.TestCase):
    def setUp(self):
        self.old=(config.SR,config.BLOCK);config.SR=48000;config.BLOCK=64
    def tearDown(self):config.SR,config.BLOCK=self.old
    def spec(self,notes,unit='seconds',tempo=120):
        inst=bounded_pluck(SOURCE)
        return RenderSpec([Track(inst,[Note(69,0,.1)]),Track(inst,[Note(p,s,d,v) for s,d,p,v in notes])],time_unit=unit,tempo=tempo)
    def reject(self,spec):
        for render in (engine.render_spec,engine.render_stems):
            with patch.object(engine.daw,'RenderEngine') as factory:
                with self.assertRaises(ValueError):render(spec)
                factory.assert_not_called()
    def test_invalid_matrix(self):
        for rate in (44100,48000,96000,192000):
            config.SR=rate
            bad=[(0,1,69.5,100),(0,1,15,100),(0,1,120,100),(0,1,69,0),(0,1,69,128),(0,1,69,90.5),(-1,1,69,100),(0,0,69,100),(0,-1,69,100),(0,float('nan'),69,100),(0,1,float('inf'),100),(1e308,1e308,69,100),(False,1,69,100),(0,1,'69',100),(0,2**31/rate,69,100),(1e308,1,69,100),(0,.25/rate,69,100),(100,1e-20,69,100)]
            for unit in ('seconds','beats'):
                for note in bad:
                    with self.subTest(rate=rate,unit=unit,note=note):self.reject(self.spec([note],unit,60))
    def test_tempo_and_unit(self):
        for tempo in (0,-1,True,'120',float('inf'),float('nan'),1e-320):
            self.reject(self.spec([(0,1,69,100)],'beats',tempo))
        self.reject(self.spec([(0,1,69,100)],'ticks'))
    def test_mutated_contract(self):
        for attr,value in [('dsp',SOURCE+'\n'),('num_voices',16),('num_voices',8.),('dynamic_voices',True),('kind','plugin')]:
            spec=self.spec([]);setattr(spec.tracks[-1].instrument,attr,value);self.reject(spec)
        for rate in (32000,48000.,True):
            config.SR=rate;self.reject(self.spec([]))
        config.SR=48000;config.BLOCK=512;self.reject(self.spec([]))
    def test_valid_boundaries(self):
        for rate in (44100,48000,96000,192000):
            config.SR=rate
            for unit in ('seconds','beats'):
                spec=self.spec([(0,1/rate,p,v) for p in range(16,120) for v in (1,127)]+[(0,(2**31-1)/rate,69,100)],unit,60)
                engine._preflight_instruments(spec)
    def test_invalid_render_duration(self):
        for duration in (True, '1', 0, -1, float('nan'), float('inf'), 10**400):
            with self.subTest(duration=repr(duration)):
                spec=self.spec([(0,.1,69,100)]);spec.duration=duration
                self.reject(spec)
    def test_explicit_crop_is_allowed(self):
        spec=self.spec([(0,1,69,100)]);spec.duration=.1
        engine._preflight_instruments(spec)
    def test_source_factory(self):
        with self.assertRaises(ValueError):bounded_pluck(SOURCE+'\n')
if __name__=='__main__':unittest.main(verbosity=2)

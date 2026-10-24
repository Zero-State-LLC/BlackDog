import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'shipwright-integration'))
from shipwright import engine, config
from shipwright.registry import Instrument, Track, Note, RenderSpec
from bounded_pluck_host_contract import validate_notes


def check(spec, track, sr):
    # Inspect raw fields before beat conversion can coerce bools.
    validate_notes([(n.start,n.dur,n.pitch,n.vel) for n in track.notes])
    validate_notes(engine._notes_seconds(spec,track))

class Integration(unittest.TestCase):
    def test_late_invalid_before_allocation(self):
        for render in (engine.render_spec,engine.render_stems):
            for unit in ('seconds','beats'):
                for bad in (Note(69.5,0,.2),Note(69,True,.2),Note(69,0,.2,0)):
                    with self.subTest(render=render.__name__,unit=unit,bad=bad):
                        inst=Instrument.faust('test','process=0;',preflight=check)
                        spec=RenderSpec([Track(inst,[Note(69,0,.2)]),Track(inst,[bad])],time_unit=unit)
                        with patch.object(engine.daw,'RenderEngine') as factory:
                            with self.assertRaises(ValueError): render(spec)
                            factory.assert_not_called()
    def test_callback_receives_original_and_rate(self):
        callback=Mock()
        inst=Instrument.faust('test','process=0;',preflight=callback)
        tr=Track(inst,[Note(69,1,2)])
        spec=RenderSpec([tr],time_unit='beats',tempo=120)
        engine._preflight_instruments(spec)
        callback.assert_called_once_with(spec,tr,config.SR)
        self.assertEqual(engine._notes_seconds(spec,tr),[(.5,1.,69,100)])
    def test_release_policy(self):
        for setting in (None,False,True):
            host=Mock(); proc=host.make_faust_processor.return_value
            inst=Instrument.faust('test','process=0;',dynamic_voices=setting)
            engine._make_source(host,'test',Track(inst,[]),[],1)
            if setting is None: self.assertNotIn('dynamic_voices',vars(proc))
            else: self.assertIs(proc.dynamic_voices,setting)
    def test_bad_policy_before_allocation(self):
        for setting in (0,1,'false'):
            for render in (engine.render_spec,engine.render_stems):
                spec=RenderSpec([Track(Instrument.faust('test','process=0;',dynamic_voices=setting),[])])
                with patch.object(engine.daw,'RenderEngine') as factory:
                    with self.assertRaises(ValueError): render(spec)
                    factory.assert_not_called()

if __name__=='__main__': unittest.main(verbosity=2)

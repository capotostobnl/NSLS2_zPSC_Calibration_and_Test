"""Small script to initialize QSPI with scale factors, faul thresholds, 
and gain and offset values of gains 1 and offset zero"""
import sys
import os

# flake8: noqa: E402
# pylint: disable=wrong-import-position
###############################################################################
#   Add outer directory to path, so app can find common dir when run standalone
if __name__ == "__main__":

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
###############################################################################
from common.initialize_dut import DUT

def initialize_qspi(dut: DUT):
    """Writes gains and offsets of 1 and 0, and sets QSPI parameters 
    for initial testing without requiring a full calibration"""
    assert dut.psc is not None

    for i, chan_name in enumerate(dut.channel_list):
        write_scale_factor(dut, i)
        write_flt_thresholds(dut, i)
        write_flt_cnt_limits(dut, i)
        initialize_gains_offsets(dut, i)
        dut.psc.write_qspi(int(chan_name)) # write all data to qspi
        print("QSPI Written")

def write_scale_factor(dut: DUT, chan_index: int):
    """Write the scale factors set in psc_models.py"""
    assert dut.psc is not None

    sf = dut.model.calibration_parameters.scale_factors
    chan = int(dut.channel_list[chan_index])

    #Scale factors
    dut.psc.set_sf_ramp_rate(chan, sf.sf_ramp_rate)
    dut.psc.set_sf_dcct_scale(chan, dut.model.calc.get_p_scale_factor(chan))
    dut.psc.set_sf_vout(chan, sf.sf_vout.as_list(dut.num_channels)[chan_index])
    dut.psc.set_sf_ignd(chan, sf.sf_ignd)
    dut.psc.set_sf_spare(chan, sf.sf_spare.as_list(dut.num_channels)[chan_index])
    dut.psc.set_sf_regulator(chan, sf.sf_regulator)
    dut.psc.set_sf_error(chan, sf.sf_error)

def write_flt_thresholds(dut: DUT, chan_index: int):
    """Write the fault threhold values set in psc_models.py"""
    assert dut.psc is not None

    #Fault thresholds
    chan = dut.channel_list[chan_index]

    flt = dut.model.calibration_parameters.fault_limits
    dut.psc.set_threshold_ovc1(chan, flt.ovc1_threshold.as_list(dut.num_channels)[chan_index])
    dut.psc.set_threshold_ovc2(chan, flt.ovc2_threshold.as_list(dut.num_channels)[chan_index])
    dut.psc.set_threshold_ovv(chan, flt.ovv_threshold.as_list(dut.num_channels)[chan_index])
    dut.psc.set_threshold_err1(chan, flt.err1_threshold)
    dut.psc.set_threshold_err2(chan, flt.err2_threshold)
    dut.psc.set_threshold_ignd(chan, flt.ignd_threshold)

def write_flt_cnt_limits(dut: DUT, chan_index: int):
    """write the fault count limit values set in psc_models.py"""
    assert dut.psc is not None
    
    #Fault Count limits
    chan = dut.channel_list[chan_index]

    flt = dut.model.calibration_parameters.fault_limits
    dut.psc.set_count_limit_ovc1(chan, flt.ovc1_flt_cnt)
    dut.psc.set_count_limit_ovc2(chan, flt.ovc2_flt_cnt)
    dut.psc.set_count_limit_ovv(chan, flt.ovv_flt_cnt)
    dut.psc.set_count_limit_err1(chan, flt.err1_flt_cnt)
    dut.psc.set_count_limit_err2(chan, flt.err2_flt_cnt)
    dut.psc.set_count_limit_ignd(chan, flt.ignd_flt_cnt)
    dut.psc.set_count_limit_dcct(chan, flt.dcct_flt_cnt)
    dut.psc.set_count_limit_flt1(chan, flt.flt1_flt_cnt)
    dut.psc.set_count_limit_flt2(chan, flt.flt2_flt_cnt)
    dut.psc.set_count_limit_flt3(chan, flt.flt3_flt_cnt)
    dut.psc.set_count_limit_on(chan, flt.flt_on_cnt)
    dut.psc.set_count_limit_heartbeat(chan, flt.flt_heartbeat_cnt)
    dut.psc.set_op_mode(chan, 3) # jump mode
    dut.psc.set_averaging(chan, 1) #PSC average mode, 167 samples

def initialize_gains_offsets(dut: DUT, chan_index: int):
    """Set all gains and offsets to unity gains and no offset"""
    assert dut.psc is not None
    
    #set PSC gains to 1 and offsets to 0
    chan = dut.channel_list[chan_index]

    # Reset Gains to 1.0
    dut.psc.set_gain_dac_setpoint(chan, 1.0)
    dut.psc.set_gain_dcct1(chan, 1.0)
    dut.psc.set_gain_dcct2(chan, 1.0)
    dut.psc.set_gain_dac_readback(chan, 1.0)
    dut.psc.set_gain_voltage(chan, 1.0)
    dut.psc.set_gain_ground(chan, 1.0)
    dut.psc.set_gain_spare(chan, 1.0)
    dut.psc.set_gain_regulator(chan, 1.0)
    dut.psc.set_gain_error(chan, 1.0)

    # Reset Offsets to 0.0
    dut.psc.set_offset_dac_setpoint(chan, 0.0)
    dut.psc.set_offset_dac_readback(chan, 0.0)
    dut.psc.set_offset_dcct1(chan, 0.0)
    dut.psc.set_offset_dcct2(chan, 0.0)
    dut.psc.set_offset_voltage(chan, 0.0)
    dut.psc.set_offset_ground(chan, 0.0)
    dut.psc.set_offset_spare(chan, 0.0)
    dut.psc.set_offset_regulator(chan, 0.0)
    dut.psc.set_offset_error(chan, 0.0)

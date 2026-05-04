from epics import caput
from Common.initialize_dut import DUT
#from Cal.psc_calibration import write_flt_cnt_limits, write_flt_thresholds, write_scale_factor
import Cal.psc_calibration as cal


ATE_IP_ADDRESS = '10.69.26.3'

def initialize_qspi(dut: DUT):
    """Executes the calibration routine, but now using the DUT parameters
    instead of hard-coding"""

    """
    psc = f"lab{{{dut.psc_num}}}Chan"

    num_chan = len(dut.model.channels)
    Ndcct = dut.model.calibration_parameters.ndcct
    chan = [str(c) for c in dut.model.channels]
    Rb = dut.model.calibration_parameters.burden_resistors.as_list(num_chan)

    sf = dut.model.calibration_parameters.scale_factors
    SF_Vout = sf.sf_vout.as_list(num_chan)
    SF_Spare = sf.sf_spare.as_list(num_chan)

    OVC1_Flt_Threshold = dut.model.calibration_parameters.ovc1_threshold.as_list(num_chan)
    OVC2_Flt_Threshold = dut.model.calibration_parameters.ovc1_threshold.as_list(num_chan)
    OVV_Flt_Threshold = dut.model.calibration_parameters.ovv_threshold.as_list(num_chan)

    for j in range(len(chan)):
        gtarget = Rb[j]*10.0 # V/A
        G = Ndcct/gtarget # power supply scale factor A/V

    for j in range(len(chan)):
        sf = dut.model.calibration_parameters.scale_factors
        flt = dut.model.calibration_parameters.fault_limits
        #Scale factors
        caput(psc+chan[j]+':SF:AmpsperSec-SP', sf.sf_ramp_rate)
        caput(psc+chan[j]+':SF:DAC_DCCTs-SP', G)
        caput(psc+chan[j]+':SF:Vout-SP', sf.sf_vout.as_list(num_chan)[j])
        caput(psc+chan[j]+':SF:Ignd-SP', sf.sf_ignd)
        caput(psc+chan[j]+':SF:Spare-SP', sf.sf_spare.as_list(num_chan)[j])
        caput(psc+chan[j]+':SF:Regulator-SP', sf.sf_regulator)
        caput(psc+chan[j]+':SF:Error-SP', sf.sf_error)

        
        #Fault thresholds
        caput(psc+chan[j]+':OVC1_Flt_Threshold-SP', OVC1_Flt_Threshold[j])
        caput(psc+chan[j]+':OVC2_Flt_Threshold-SP', OVC2_Flt_Threshold[j])
        caput(psc+chan[j]+':OVV_Flt_Threshold-SP', OVV_Flt_Threshold[j])
        caput(psc+chan[j]+':ERR1_Flt_Threshold-SP', flt.err1_threshold)
        caput(psc+chan[j]+':ERR2_Flt_Threshold-SP', flt.err2_threshold)
        caput(psc+chan[j]+':IGND_Flt_Threshold-SP', flt.ignd_threshold)

        #Fault Count limits
        caput(psc+chan[j]+':OVC1_Flt_CntLim-SP', flt.ovc1_flt_cnt)
        caput(psc+chan[j]+':OVC2_Flt_CntLim-SP', flt.ovc2_flt_cnt)
        caput(psc+chan[j]+':OVV_Flt_CntLim-SP', flt.ovv_flt_cnt)
        caput(psc+chan[j]+':ERR1_Flt_CntLim-SP', flt.err1_flt_cnt)
        caput(psc+chan[j]+':ERR2_Flt_CntLim-SP', flt.err2_flt_cnt)
        caput(psc+chan[j]+':IGND_Flt_CntLim-SP', flt.ignd_flt_cnt)
        caput(psc+chan[j]+':DCCT_Flt_CntLim-SP', flt.dcct_flt_cnt)
        caput(psc+chan[j]+':FLT1_Flt_CntLim-SP', flt.flt1_flt_cnt)
        caput(psc+chan[j]+':FLT2_Flt_CntLim-SP', flt.flt2_flt_cnt)
        caput(psc+chan[j]+':FLT3_Flt_CntLim-SP', flt.flt3_flt_cnt)
        caput(psc+chan[j]+':ON_Flt_CntLim-SP', flt.flt_on_cnt)
        caput(psc+chan[j]+':HeartBeat_Flt_CntLim-SP', flt.flt_heartbeat_cnt)
            
        caput(psc+chan[j]+':DAC_OpMode-SP', 3) # jump mode
        caput(psc+chan[j]+':AveMode-SP', 1) #PSC average mode, 167 samples


        #set PSC gains to 1 and offsets to 0
        caput(psc+chan[j]+':DACSetPt-Gain-SP', 1.0)
        caput(psc+chan[j]+':DCCT1-Gain-SP', 1.0)
        caput(psc+chan[j]+':DCCT2-Gain-SP', 1.0)
        caput(psc+chan[j]+':DAC-Gain-SP', 1.0)
        caput(psc+chan[j]+':Volt-Gain-SP', 1.0)
        caput(psc+chan[j]+':Gnd-Gain-SP', 1.0)
        caput(psc+chan[j]+':Spare-Gain-SP', 1.0)
        caput(psc+chan[j]+':Reg-Gain-SP', 1.0)
        caput(psc+chan[j]+':Error-Gain-SP', 1.0)
        
        caput(psc+chan[j]+':DACSetPt-Offset-SP', 0.0)
        caput(psc+chan[j]+':DCCT1-Offset-SP', 0.0)
        caput(psc+chan[j]+':DCCT2-Offset-SP', 0.0)
        caput(psc+chan[j]+':DAC-Offset-SP', 0.0)
        caput(psc+chan[j]+':Volt-Offset-SP', 0.0)
        caput(psc+chan[j]+':Gnd-Offset-SP', 0.0)
        caput(psc+chan[j]+':Spare-Offset-SP', 0.0)
        caput(psc+chan[j]+':Reg-Offset-SP', 0.0)
        caput(psc+chan[j]+':Error-Offset-SP', 0.0)"""

    cal.init_local_vars(dut)

    for chan_index in range(cal._num_chan):
        cal.write_scale_factor(dut, chan_index)
        cal.write_flt_thresholds(dut, chan_index)
        cal.write_flt_cnt_limits(dut, chan_index)

        caput(cal._psc+cal._chan[chan_index]+':WriteQspi-SP', 1) # write all data to qspi

        print("QSPI Written")


if __name__ == "__main__":
    local_dut = DUT()
    local_dut.prompt_inputs()
    initialize_qspi(local_dut)
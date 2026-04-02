from epics import caput
from Common.initialize_dut import DUT


ATE_IP_ADDRESS = '10.69.26.3'


def initialize_qspi(dut: DUT):
    """Executes the calibration routine, but now using the DUT parameters
    instead of hard-coding"""

    psc = f"lab{{{dut.psc_num}}}Chan"

    num_chan = len(dut.model.channels)
    Ndcct = dut.model.calibration_parameters.ndcct
    chan = [str(c) for c in dut.model.channels]
    Rb = dut.model.calibration_parameters.burden_resistors.as_list(num_chan)

    sf = dut.model.psc_scale_factors
    SF_Vout = sf.sf_vout.as_list(num_chan)
    SF_Spare = sf.sf_spare.as_list(num_chan)

    flt_thresholds = dut.model.psc_fault_thresholds_limits
    OVC1_Flt_Threshold = flt_thresholds.ovc1_threshold.as_list(num_chan)
    OVC2_Flt_Threshold = flt_thresholds.ovc2_threshold.as_list(num_chan)
    OVV_Flt_Threshold = flt_thresholds.ovv_threshold.as_list(num_chan)

    for j in range(len(chan)):
        gtarget = Rb[j]*10.0 # V/A
        G = Ndcct/gtarget # power supply scale factor A/V

    for j in range(len(chan)):
        #Scale factors
        caput(psc+chan[j]+':SF:AmpsperSec-SP', 4.0)
        caput(psc+chan[j]+':SF:DAC_DCCTs-SP', G)
        caput(psc+chan[j]+':SF:Vout-SP', SF_Vout[j])
        caput(psc+chan[j]+':SF:Ignd-SP', 1.0)
        caput(psc+chan[j]+':SF:Spare-SP', SF_Spare[j])
        caput(psc+chan[j]+':SF:Regulator-SP', 1.0)
        caput(psc+chan[j]+':SF:Error-SP', 1.0)
        

        #Fault thresholds
        caput(psc+chan[j]+':OVC1_Flt_Threshold-SP', OVC1_Flt_Threshold[j])
        caput(psc+chan[j]+':OVC2_Flt_Threshold-SP', OVC2_Flt_Threshold[j])
        caput(psc+chan[j]+':OVV_Flt_Threshold-SP', OVV_Flt_Threshold[j])
        caput(psc+chan[j]+':ERR1_Flt_Threshold-SP', 10)
        caput(psc+chan[j]+':ERR2_Flt_Threshold-SP', 10)
        caput(psc+chan[j]+':IGND_Flt_Threshold-SP', 10)
        
        #Fault Count limits
        caput(psc+chan[j]+':OVC1_Flt_CntLim-SP', 0.01)
        caput(psc+chan[j]+':OVC2_Flt_CntLim-SP', 0.01)
        caput(psc+chan[j]+':OVV_Flt_CntLim-SP', 0.01)
        caput(psc+chan[j]+':ERR1_Flt_CntLim-SP', 0.1)
        caput(psc+chan[j]+':ERR2_Flt_CntLim-SP', 0.1)
        caput(psc+chan[j]+':IGND_Flt_CntLim-SP', 0.2)
        caput(psc+chan[j]+':DCCT_Flt_CntLim-SP', 0.2)
        caput(psc+chan[j]+':FLT1_Flt_CntLim-SP', 0.1)
        caput(psc+chan[j]+':FLT2_Flt_CntLim-SP', 3)
        caput(psc+chan[j]+':FLT3_Flt_CntLim-SP', 0.5)
        caput(psc+chan[j]+':ON_Flt_CntLim-SP', 3)
        caput(psc+chan[j]+':HeartBeat_Flt_CntLim-SP', 3)
            
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
        caput(psc+chan[j]+':Error-Offset-SP', 0.0)

        caput(psc+chan[j]+':WriteQspi-SP', 1) # write all data to qspi

        print("QSPI Written")


if __name__ == "__main__":
    local_dut = DUT()
    local_dut.prompt_inputs()
    initialize_qspi(local_dut)
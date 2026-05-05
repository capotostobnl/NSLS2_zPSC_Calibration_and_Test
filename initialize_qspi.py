from epics import caput
from Common.initialize_dut import DUT
#from Cal.psc_calibration import write_flt_cnt_limits, write_flt_thresholds, write_scale_factor
import Cal.psc_calibration as cal


ATE_IP_ADDRESS = '10.69.26.3'

def initialize_qspi(dut: DUT):
    """Executes the calibration routine, but now using the DUT parameters
    instead of hard-coding"""

    cal.init_local_vars(dut)

    for chan_index in range(cal._num_chan):
        cal.write_scale_factor(dut, chan_index)
        cal.write_flt_thresholds(dut, chan_index)
        cal.write_flt_cnt_limits(dut, chan_index)
        cal.initialize_gains_offsets(dut, chan_index)

        caput(cal._psc+cal._chan[chan_index]+':WriteQspi-SP', 1) # write all data to qspi

        print("QSPI Written")


if __name__ == "__main__":
    local_dut = DUT()
    local_dut.prompt_inputs()
    initialize_qspi(local_dut)
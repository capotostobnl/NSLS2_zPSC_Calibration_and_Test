"""
PSC Calibration Module
This module loads values for QSPI flash, and calculates required gains and
offsets to calibrate PSC ADCs and DACs using external traceable calibrated
instruments and reference standards. 
"""
from typing import List
import time
import sys
import os
from datetime import datetime
import numpy as np
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
from instrument_modules.hp3458a_prologix import HP3458A
from instrument_modules.instrument_addresses import DMM_PORT, DMM_BAUD, \
     DMM_GPIB_ADDR, ATE_PREFIX
from common.initialize_dut import DUT
from common.epics_adapters.ate_epics import ATE

#  Formatting Constants for tables
HEAD_FMT = "{:>38}{:>14}{:>14}{:>14}"
DATA_FMT = "{:<29}{:>9.6f}{:>14.6f}{:>14.6f}{:>14.6f}"
VAL_FMT  = "{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}"



def initialize_qspi(dut: DUT):
    """Writes gains and offsets of 1 and 0, and sets QSPI parameters 
    for initial testing without requiring a full calibration"""

    for i, chan_name in enumerate(dut.channel_list):
        write_scale_factor(dut, i)
        write_flt_thresholds(dut, i)
        write_flt_cnt_limits(dut, i)
        initialize_gains_offsets(dut, i)
        dut.psc.write_qspi(int(chan_name), 1) # write all data to qspi
        print("QSPI Written")

def write_scale_factor(dut: DUT, chan_index: int):
    """Write the scale factors set in psc_models.py"""
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
    #set PSC gains to 1 and offsets to 0
    chan = dut.channel_list[chan_index]

    dut.psc.set_gain_dac_setpoint(chan, 1.0)
    dut.psc.set_gain_dcct1(chan, 1.0)
    dut.psc.set_gain_dcct2(chan, 1.0)
    dut.psc.set_gain_dac_setpoint(chan, 1.0)
    dut.psc.set_gain_voltage(chan, 1.0)
    dut.psc.set_gain_ground(chan, 1.0)
    dut.psc.set_gain_spare(chan, 1.0)
    dut.psc.set_gain_regulator(chan, 1.0)
    dut.psc.set_gain_error(chan, 1.0)

    dut.psc.set_offset_dac_setpoint(chan, 0.0)
    dut.psc.set_offset_dcct1(chan, 0.0)
    dut.psc.set_offset_dcct2(chan, 0.0)
    dut.psc.set_offset_dac_setpoint(chan, 0.0)
    dut.psc.set_offset_voltage(chan, 0.0)
    dut.psc.set_offset_ground(chan, 0.0)
    dut.psc.set_offset_spare(chan, 0.0)
    dut.psc.set_offset_regulator(chan, 0.0)
    dut.psc.set_offset_error(chan, 0.0)

def run_calibration(dut: DUT):
    """Executes the calibration routine, but now using the DUT parameters
    instead of hard-coding"""

    dmm = HP3458A(DMM_PORT, DMM_BAUD, 30, DMM_GPIB_ADDR)
    dmm.initialize()

    ate = ATE(prefix=ATE_PREFIX)

    formatted_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cal_params = dut.model.calibration_parameters

    designation = dut.model.designation
    n_dcct = cal_params.ndcct
    burden_resistor = cal_params.burden_resistors.as_list(dut.num_channels)

    print(f"Calibrating PSC model {designation} SN {dut.psc_sn}")

    num_runs=5 # of runs per channel

    def set_atsdac_cal_source(setpoint_amps):
        ate.set_cal_dac(setpoint_amps * 50)  # 50V/A

    def measure_testpoints(current_measured: float,
                           setpoint: float,
                           verification: bool,
                           physical_chan: int,
                           dmm_offs: float,
                           dut: DUT,
                           dmm: HP3458A
                           ) -> List[float]:
        """Adjusts the PSC for null error and takes calibrated 
        readbacks."""

        # Set Local Parameters for the DUT object
        n_dcct = dut.model.calibration_parameters.ndcct
        p_scale = dut.model.calc.get_p_scale_factor(physical_chan)
        current_full_scale = 1.0 / burden_resistor[chan_index] # max burden current


        # Set Calibration Source
        for _ in range(4):
            set_atsdac_cal_source(current_measured)
            time.sleep(0.5)

        # Validate source config
        adc1 = dut.psc.get_dcct1(physical_chan)
        time.sleep(1)
        expected = abs(current_measured * n_dcct)
        time.sleep(1)
        if (abs(adc1)-expected) > (0.3*expected):
            print("Error setting calibration DAC setpoint. Try again.")
            sys.exit()

        settling_time=2

        # choose current_full_scale*2 as max allowable value of
        # error for null.
        error_limit = current_full_scale * 2

        for adj_attempt in range(13):  # 0 to 12...
            dut.psc.set_dac_setpt(physical_chan, setpoint)
            time.sleep(settling_time)
            err = dut.psc.get_error_i(physical_chan)

            # Exit condition: Error is low enough (skip first run to ensure update)
            if adj_attempt > 0 and abs(err) <= error_limit:
                break

            if adj_attempt == 12:
                raise RuntimeError("Calibration failed. Could not null error. Try again.")


            setpoint = setpoint - (err/400*p_scale)
            print(f"adjustment {adj_attempt}: Error ={err:.6f}")

        #  Measurement Loop
        if verification:
            tolerance = 0.0002
        else:
            tolerance = 0.02

        threshold = tolerance * current_full_scale * n_dcct

        for _ in range(4):  # 4 attempts

            adc1 = dut.psc.get_dcct1(physical_chan)
            adc2 = dut.psc.get_dcct2(physical_chan)
            adc3 = dut.psc.get_dac(physical_chan)
            dmm_raw = dmm.get_reading()

            # Calculate scaled DMM current
            dmm_current = (dmm_raw - dmm_offs) * gtarget * p_scale

            # Validate readings
            check1 = abs(adc1 + setpoint) < threshold
            check2 = abs(adc2 + setpoint) < threshold
            check3 = abs(adc3 - setpoint) < threshold
            check4 = abs(dmm_current + setpoint) < threshold

            if all([check1, check2, check3, check4]):
                return[dmm_current, setpoint, adc1, adc2, adc3, err]

            time.sleep(1.0)

        # If all three attempts fail...
        print(f"adc1 = {adc1:3.5f}")
        print(f"adc2 = {adc2:3.5f}")
        print(f"adc3 = {adc3:3.5f}")
        print(f"sp = {setpoint:3.5f}")
        print("")
        raise RuntimeError("Calibration failed. Bad verification measurement(s). Try again.")


    def compute_m_b(y0, y1):
        m1 = (y1[2]-y0[2])/(y1[0]-y0[0])
        m2 = (y1[3]-y0[3])/(y1[0]-y0[0])
        m3 = (y1[4]-y0[4])/(y1[1]-y0[1])
        mdac = (y1[1]-y0[1])/(y1[0]-y0[0])
        b1 = y0[2]-m1*y0[0]
        b2 = y0[3]-m2*y0[0]
        b3 = y0[4]-m3*y0[1]
        bdac = y0[1]-mdac*y0[0]

        return -mdac, m1, m2, m3, -bdac, b1, b2, b3

    def print_testpoints(y, v):
        if v=='v':
            print(f"{'Itest':>14}{'dacSP':>14}{'dcct1':>14}{'dcct2':>14}"
                  f"{'dacRB':>14}{'err':>14}")
        print(f"{y[0]:>14.6f}{y[1]:>14.6f}{y[2]:>14.6f}{y[3]:>14.6f}"
              f"{y[4]:>14.6f}{y[5]:>14.6f}")

    def fprint_testpoints(y, v):
        if v=='v':
            fp.write(f"{'Itest':>12}{'dacSP':>12}{'dcct1':>12}{'dcct2':>12}"
                     f"{'dacRB':>12}{'err':>12}\n")
        fp.write(f"{y[0]:>12.6f}{y[1]:>12.6f}{y[2]:>12.6f}{y[3]:>12.6f}"
                 f"{y[4]:>12.6f}{y[5]:>12.6f}\n")


    #now = datetime.now()
    #date_str = now.strftime("%Y-%m-%d_%H.%M.%S")

    #file_str = "psc_calibration_temp_" + SN + ".doc"
    file_str = "psc_calibration_temp.doc"
    fp = open(file_str, "w", encoding="utf-8")
    fp.write("Report of Calibration\n")
    fp.write(f"PSC {designation} S/N {dut.psc_sn}\n")
    fp.write(formatted_date_time+"\n\n")
    #fp.write("Calibration Current standard: Keithley 2401\n")
    fp.write("Calibration Current standard: BNL PSC ATE S/N 001\n")
    #fp.write("Calibration Volt standard: HP 3458A-002 S/N 2823A 06900\n")
    fp.write("Calibration Volt standard: HP 3458A-002 S/N 2823A 23647\n")
    fp.write("Calibration Resistance standard: Fluke 742A-1 S/N 1063008\n")
    fp.write("End Header\n\n\n")

    for chan_index, physical_chan in enumerate(dut.channel_list): # loop through channels
        _psc = dut.psc_chan_prefix
        dut.num_channels = dut.num_channels

        #turn all channels off
        dut.psc.set_power_on1(ch=1, val=0)
        dut.psc.set_power_on1(ch=2, val=0)
        dut.psc.set_power_on1(ch=3, val=0)
        dut.psc.set_power_on1(ch=4, val=0)
        print("Turning all channels off...")

        #put all ATE channels in test mode
        for _chan in range(1, 5):
            ate.set_mode(_chan, 0)
            time.sleep(.5)

        #turn calibration source off
        ate.set_cal_state(0)

        #get dmm zero reading
        dmm_offs = dmm.get_reading() # reference current i0
        print(f"DMM zero offset reading: {dmm_offs:.7f}")

        #set channel j to cal mode
        ate.set_mode(physical_chan, 1)

        #turn on cal source
        ate.set_cal_state(1)

        #gtarget = burden_resistor[chan_index]*10.0 # V/A
        gtarget = dut.model.calc.get_s_scale_factor(physical_chan)

        #G = n_dcct/gtarget # power supply scale factor A/V
        p_scale = dut.model.calc.get_p_scale_factor(physical_chan)

        current_full_scale = 1.0/burden_resistor[chan_index] # max burden current
        #print(current_full_scale)
        current_low_ref = -1.0/n_dcct # 1 A
        sp0 = 1.0
        current_high_ref = -(float(round(current_full_scale*0.9*1000)/1000)) # round to nearest mA

        # sp1 = float(int(10*G*0.9)) # must be close to current
        # setting to keep error from saturating
        sp1 = float(round(10*p_scale*0.9))
        #print("%3.6f   %.6f   %3.6f   %3.6f" % (sp0, sp1, current_low_ref, current_high_ref))
        y0 = np.zeros(6) # readbacks
        y1 = np.zeros(6)
        cal_results = np.zeros((num_runs,8)) # gains/offsets multiple runs
        if abs(current_high_ref) > 0.11:
            dmm.set_range(1.0)
        if abs(current_high_ref) <= 0.11:
            dmm.set_range(0.1)

        print(_psc+physical_chan)
        print(f"Burden resistor = {burden_resistor[chan_index]:3.4f}")

        write_scale_factor(dut, chan_index)
        write_flt_thresholds(dut, chan_index)
        write_flt_cnt_limits(dut, chan_index)

        for k in range(num_runs): # N runs on each channel
            print("")
            print(f"Run #: {k+1}")
            #CHx
            #Calibration

            initialize_gains_offsets(dut, chan_index)

            print("Measuring initial gains and offsets")
            if k==num_runs-1:
                fp.write(_psc+physical_chan+"\n")
                fp.write(f"Burden resistor = {burden_resistor[chan_index]:%3.4f}\n\n")
                fp.write("Measuring initial gains and offsets\n")
            #print("Measuring i0")
            y0 = measure_testpoints(current_low_ref, sp0, 0, physical_chan, dmm_offs, dut, dmm)
            print_testpoints(y0,'v')
            if k==num_runs-1:
                fprint_testpoints(y0,'v')

            y1 = measure_testpoints(current_high_ref, sp1, 0, physical_chan, dmm_offs, dut, dmm)
            #print("   I      dacSP      dcct1      dcct2      dacRB      err")
            print_testpoints(y1,'')
            if k==num_runs-1:
                fprint_testpoints(y1,'')

            #Initial measured gains/offsets
            [mdac, m1, m2, m3, bdac, b1, b2, b3] = compute_m_b(y0, y1)

            print("")
            print(f"{'dacSP':>40}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}")
            print(f"{'Initial measured offsets: '}{bdac:>14.6f}{b1:>14.6f}"
                  f"{b2:>14.6f}{0:>14.6f}") #initial measured offsets

            print(f"{'Initial measured gains:   '}{mdac:>14.6f}{m1:>14.6f}"
                  f"{m2:>14.6f}{m3:>14.6f}") #initial measured gains

            print(f"{'Gain corrections:         '}{mdac:>14.6f}{1/m1:>14.6f}"
                  f"{1/m2:>14.6f}{1:>14.6f}")

            print("")
            print("Writing gain and offset corrections for dacSP, dcct1, and dcct2 to PSC")

            if k==num_runs-1:
                fp.write("\n")
                fp.write(f"{'dacSP':>40}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
                fp.write(f"{'Initial measured offsets: '}{bdac:>14.6f}{b1:>14.6f}"
                         f"{b2:>14.6f}{0:>14.6f}\n") #initial measured offsets

                fp.write(f"{'Initial measured gains:   '}{mdac:>14.6f}{m1:>14.6f}"
                         f"{m2:>14.6f}{m3:>14.6f}\n") #initial measured gains

                fp.write(f"{'Gain corrections:         '}{mdac:>14.6f}{1/m1:>14.6f}"
                         f"{1/m2:>14.6f}{1:>14.6f}\n")

                fp.write("\n")
                fp.write("Writing gain and offset corrections for dacSP, dcct1, and dcct2 to PSC\n")


            time.sleep(2)
            # offset constants are subtracted from ADC readings and DAC setpoint
            # write m1, m2, mdac, b1, b2, bdac to PSC (do not write m3, b3)
            dut.psc.set_gain_dcct1(physical_chan, 1/m1)
            dut.psc.set_gain_dcct2(physical_chan, 1/m2)
            dut.psc.set_gain_dac_setpoint(physical_chan, mdac)
            dut.psc.set_offset_dcct1(physical_chan, b1)
            dut.psc.set_offset_dcct2(physical_chan, b2)
            dut.psc.set_offset_dac_setpoint(physical_chan, bdac)

            print("")
            print("Measuring DAC readback gain and offset")
            #print("Measuring sp0")
            # #DAC readback corrections
            dut.psc.set_dac_setpt(physical_chan, sp0)
            time.sleep(1)
            adc3 = dut.psc.get_dac(physical_chan)
            y0[4] = adc3
            print("DAC SP   DAC RB")
            print(f"{sp0:2.6f}   {y0[4]:2.6f} ")

            if k==num_runs-1:
                fp.write("\n")
                fp.write("Measuring DAC readback gain and offset\n")
                #fp.write("Measuring sp0\n")
                fp.write("DAC SP   DAC RB\n")
                fp.write(f"{sp0:2.6f}   {y0[4]:2.6f} \n")

            #print("Measuring sp1")
            dut.psc.set_dac_setpt(physical_chan, sp1)
            time.sleep(1)
            adc3 = adc3 = dut.psc.get_dac(physical_chan)
            y1[4] = adc3
            print(f"{sp1:2.6f}   {y1[4]:2.6f} ", end="")
            print("")
            if k==num_runs-1:
                fp.write(f"{sp1:2.6f}   {y1[4]:2.6f} \n")

            m3 = (y1[4]-y0[4])/(sp1-sp0)
            b3 = y0[4]-m3*sp0

            fp.write(f"Measured offset: {b3}\n") #initial measured offsets
            fp.write(f"Measured gain: {m3}\n") #initial measured gains
            fp.write(f"Gain correction: {1/m3}\n")

            print("")
            print("Writing gain and offset constants for dacRB to PSC")
            time.sleep(2)
            # write m3, b3 to PSC
            dut.psc.set_gain_dac_readback(physical_chan, 1/m3)
            dut.psc.set_offset_dac_readback(physical_chan, b3)

            if k==num_runs-1:
                fp.write("\n")
                fp.write(f"Measured offset: {b3}\n") #initial measured offsets
                fp.write(f"Measured gain: {m3}\n") #initial measured gains
                fp.write(f"Gain correction: {1/m3}\n")
                fp.write("\n")
                fp.write("Writing gain and offset constants for dacRB to PSC\n\n")


            # Verification
            print("\n\n")
            print("Verification")
            if k==num_runs-1:
                fp.write("Verification\n")

            y0 = measure_testpoints(current_low_ref, sp0, 1, physical_chan,
                                    dmm_offs, dut, dmm)
            print_testpoints(y0,'v')
            if k==num_runs-1:
                fprint_testpoints(y0,'v')
            y1 = measure_testpoints(current_high_ref, sp1, 1, physical_chan,
                                    dmm_offs, dut, dmm)
            print_testpoints(y1,'')
            if k==num_runs-1:
                fprint_testpoints(y1,'')


            #Final measured gains/offsets
            [mdac, m1, m2, m3, bdac, b1, b2, b3] = compute_m_b(y0, y1)

            print("")
            print("")
            print(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}")
            print(f"{'Final measured offsets: '}{bdac:>14.6f}{b1:>14.6f}{b2:>14.6f}{b3:>14.6f}")
            print(f"{'Final measured gains:   '}{mdac:>14.6f}{m1:>14.6f}{m2:>14.6f}{m3:>14.6f}")

            print("\n\n")

            if k==num_runs-1:
                fp.write("\n")
                fp.write("\n")
                fp.write(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
                fp.write(f"{'Final measured offsets: '}{bdac:>14.6f}{b1:>14.6f}"
                         f"{b2:>14.6f}{b3:>14.6f}\n")

                fp.write(f"{'Final measured gains:   '}{mdac:>14.6f}{m1:>14.6f}"
                         f"{m2:>14.6f}{m3:>14.6f}\n")
                fp.write("\n\n")

            cal_results[k,:] = [mdac, m1, m2, m3, bdac, b1, b2, b3]


        #np.set_printoptions(precision=6, suppress=True)

        m_avg = np.mean(cal_results, axis=0) # 0 is mean of each column. 1 is mean of each row
        m_std = np.std(cal_results, axis=0)
        print("")
        print("")
        print("")
        print(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}")
        print(f"{'Final meas. offsets mean: '}{m_avg[4]:>9.6f}{m_avg[5]:>14.6f}"
              f"{m_avg[6]:>14.6f}{m_avg[7]:>14.6f}")
        print(f"{'Final meas. offsets stdev:'}{m_std[4]:>9.6f}{m_std[5]:>14.6f}"
              f"{m_std[6]:>14.6f}{m_std[7]:>14.6f}")
        print(f"{'Final meas. gains mean:   '}{m_avg[0]:>9.6f}{m_avg[1]:>14.6f}"
              f"{m_avg[2]:>14.6f}{m_avg[3]:>14.6f}")
        print(f"{'Final meas. gains stdev:  '}{m_std[0]:>9.6f}{m_std[1]:>14.6f}"
              f"{m_std[2]:>14.6f}{m_std[3]:>14.6f}")
        print("")

        #if k==num_runs-1:
        fp.write("\n")
        fp.write(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
        fp.write(f"{'Final measured offsets mean: '}{m_avg[4]:>9.6f}{m_avg[5]:>14.6f}"
                 f"{m_avg[6]:>14.6f}{m_avg[7]:>14.6f}\n")
        fp.write(f"{'Final measured offsets stdev:'}{m_std[4]:>9.6f}{m_std[5]:>14.6f}"
                 f"{m_std[6]:>14.6f}{m_std[7]:>14.6f}\n")
        fp.write(f"{'Final measured gains mean:   '}{m_avg[0]:>9.6f}{m_avg[1]:>14.6f}"
                 f"{m_avg[2]:>14.6f}{m_avg[3]:>14.6f}\n")
        fp.write(f"{'Final measured gains stdev:  '}{m_std[0]:>9.6f}{m_std[1]:>14.6f}"
                 f"{m_std[2]:>14.6f}{m_std[3]:>14.6f}\n")
        fp.write("\n")

        print(f"Saving channel {physical_chan} calibration data to qspi\n")
        fp.write(f"Saving channel {physical_chan} calibration constants to qspi\n")
        if chan_index>0:
            fp.write("\n\n\n\n\n")
        if chan_index==(dut.num_channels-1):
            fp.write("Test data reviewed by ______________________________   Date_____________")
        fp.write("\n\n")
        fp.write(f"\nPage {chan_index+1} of {dut.num_channels}")
        dut.psc.write_qspi(physical_chan) # write all data to qspi

        if chan_index<3:
            #fp.write("\r\n") # form feed aka page break
            fp.write("\f") # form feed aka page break

    print("Calibration complete.")


    fp.close()

    #turn calibration source off
    set_atsdac_cal_source(0)

    #put all ATE channels in test mode
    for _chan in range(1, 5):
        ate.set_mode(_chan, 0)
        time.sleep(0.5)

    file_str1 = os.path.join(dut.cal_report_dir, f"{designation}{dut.psc_sn}_{dut.dir_timestamp}")
    os.system(f'cp "{file_str}" "{file_str1}.doc"')


if __name__ == "__main__":
    local_dut = DUT()
    local_dut.prompt_inputs()
    run_calibration(local_dut)

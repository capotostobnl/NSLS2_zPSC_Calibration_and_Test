# pylint: disable=line-too-long, missing-module-docstring, missing-function-docstring, missing-class-docstring

import time
import sys
import socket
import os
from datetime import datetime
import numpy as np
from epics import caget, caput
import serial
from Common.instrument_addresses import ATE_IP_ADDRESS

# flake8: noqa: E402
###############################################################################
#   Add outer directory to path, so app can find Common dir when run standalone
if __name__ == "__main__":

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
###############################################################################
from Common.initialize_dut import DUT

#  Formatting Constants for tables
HEAD_FMT = "{:>38}{:>14}{:>14}{:>14}"
DATA_FMT = "{:<29}{:>9.6f}{:>14.6f}{:>14.6f}{:>14.6f}"
VAL_FMT  = "{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}"



def initialize_qspi(dut: DUT):
    """Writes gains and offsets of 1 and 0, and sets QSPI parameters 
    for initial testing"""

    _psc = dut.psc_chan_prefix
    _chan = dut.channel_list

    for chan_index in range(dut.num_channels):
        write_scale_factor(dut, chan_index)
        write_flt_thresholds(dut, chan_index)
        write_flt_cnt_limits(dut, chan_index)
        initialize_gains_offsets(dut, chan_index)
        caput(_psc+_chan[chan_index]+':WriteQspi-SP', 1) # write all data to qspi
        print("QSPI Written")

def write_scale_factor(dut: DUT, chan_index: int):
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
    #set PSC gains to 1 and offsets to 0
    _psc = dut.psc_chan_prefix
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
    _num_chan = dut.num_channels

    formatted_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cal_params = dut.model.calibration_parameters

    designation = dut.model.designation
    n_dcct = cal_params.ndcct
    burden_resistor = cal_params.burden_resistors.as_list(_num_chan)

    string1 = f"Calibrating PSC model {designation} SN {dut.psc_sn}"
    print(string1)

    num_runs=5 # of runs per channel

    ser1 = serial.Serial('/dev/ttyUSB0', 115200, timeout=30)
    x = ser1.write(b"++addr 24\n")
    x = ser1.write(b"++auto 0\n")
    x = ser1.write(b"AZERO ON\n")
    x = ser1.write(b"NPLC 30\n")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        server_address = (ATE_IP_ADDRESS, 5000)
        #sock.bind (server_address)
    except Exception as err:
        print(f"Socket error: {err}s")

    def get_dmm():
        ser1.write("TARM SGL\n".encode('utf-8'))
        time.sleep(1)
        ser1.write(b"++auto 1\n")
        data = ser1.read_until(b'\n',1000)
        ser1.write(b"++auto 0\n")
        return data

    def set_atsdac_cal_source(setpoint_amps):
        y = str(setpoint_amps*50) # 50V/A
        sock.sendto(b'CALDAC' + y.encode('UTF-8') + b'\n', server_address)

    def measure_testpoints(current_measured, sp, verbose, verification):
        _psc = dut.psc_chan_prefix
        #print("%3.6f" % I)
        #i0 = -current_full_scale*0.1 # unipolar
        #set_keithley2401(I)
        for i in range(4):
            set_atsdac_cal_source(current_measured)
            time.sleep(0.5)
        adc1 = caget(f'{_psc}{physical_chan}:DCCT1-I')
        #print(adc1)
        #print(I*n_dcct)
        time.sleep(1)
        if (abs(adc1)-abs(current_measured*n_dcct)) > 0.3*abs(current_measured*n_dcct):
            print("Error setting calibration DAC setpoint. Try again.")
            sys.exit()
        #time.sleep(5)
        if verbose:
            print("Adjusting DAC for null error")
        #td = [2, 2, 2] # wait time after changing DAC
        td=2
        #err=0
        i=0
        caput(f'{_psc}{physical_chan}:DAC_SetPt-SP', sp)    # set DAC
        time.sleep(td)
        err = caget(f'{_psc}{physical_chan}:Error-I') # get err
        #for i in range(3):
        # choose current_full_scale*2 as max allowable value of error for null. i==0 condition ensures that loop runs once.
        while abs(err)>current_full_scale*2 and i<12 or i==0:
            print(f"adjustment {i}")
            dac = sp - err/400*p_scale
            sp = dac
            caput(f'{_psc}{physical_chan}:DAC_SetPt-SP', sp)    # set DAC
            time.sleep(td)
            err = caget(f'{_psc}{physical_chan}:Error-I') # get err
            i+=1

        if i == 12:
            print("Calibration failed. Could not null error. Try again.")
            sys.exit()

        i=0
        x=0
        if verification==0:
            while(i<4 and x==0):
                adc1 = caget(f'{_psc}{physical_chan}:DCCT1-I')
                adc2 = caget(f'{_psc}{physical_chan}:DCCT2-I')
                adc3 = caget(f'{_psc}{physical_chan}:DAC-I')
                dmm = float(get_dmm().decode('utf-8')) - dmm_offs  # reference current i0
                i+=1
                if abs(adc1+sp) < 0.02*current_full_scale*n_dcct and abs(adc2+sp) < 0.02*current_full_scale*n_dcct and \
                abs(adc3-sp) < 0.02*current_full_scale*n_dcct and abs(dmm*gtarget*p_scale+sp) < 0.02*current_full_scale*n_dcct:
                    x=1 # if all readings good, break loop
                time.sleep(1)
            if i == 4:
                print(f"adc1 = {adc1:3.5f}")
                print(f"adc2 = {adc2:3.5f}")
                print(f"adc3 = {adc3:3.5f}")
                print(f"sp = {sp:3.5f}")
                dmm_scaled = dmm*gtarget*p_scale
                print(f"dmm = {dmm_scaled:3.5f}")
                print("Calibration failed. Bad initial measurement(s). Try again.")
                sys.exit()

        if verification==1:
            while(i<4 and x==0):
                adc1 = caget(f'{_psc}{physical_chan}:DCCT1-I')
                adc2 = caget(f'{_psc}{physical_chan}:DCCT2-I')
                adc3 = caget(f'{_psc}{physical_chan}:DAC-I')
                dmm = float(get_dmm().decode('utf-8')) - dmm_offs # reference current i0
                i+=1
                if abs(adc1+sp) < 0.0002*current_full_scale*n_dcct and abs(adc2+sp) < 0.0002*current_full_scale*n_dcct and \
                abs(adc3-sp) < 0.0002*current_full_scale*n_dcct and abs(dmm*gtarget*p_scale+sp) < 0.0002*current_full_scale*n_dcct:
                    x=1 # if all readings good, break loop
                time.sleep(1)
            if i == 4:
                print(f"adc1 = {adc1:3.5f}")
                print(f"adc2 = {adc2:3.5f}")
                print(f"adc3 = {adc3:3.5f}")
                print(f"sp = {sp:3.5f}")
                print("Calibration failed. Bad verification measurement(s). Try again.")
                sys.exit()




        #caput(f'{_psc}{physical_chan}:SF:AmpsperSec-SP', 10)
        #time.sleep(1)

        return [dmm*gtarget*p_scale, dac, adc1, adc2, adc3, err]


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
            print(f"{'Itest':>14}{'dacSP':>14}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}{'err':>14}")
        print(f"{y[0]:>14.6f}{y[1]:>14.6f}{y[2]:>14.6f}{y[3]:>14.6f}{y[4]:>14.6f}{y[5]:>14.6f}")

    def fprint_testpoints(y, v):
        if v=='v':
            fp.write(f"{'Itest':>12}{'dacSP':>12}{'dcct1':>12}{'dcct2':>12}{'dacRB':>12}{'err':>12}\n")
        fp.write(f"{y[0]:>12.6f}{y[1]:>12.6f}{y[2]:>12.6f}{y[3]:>12.6f}{y[4]:>12.6f}{y[5]:>12.6f}\n")


    #now = datetime.now()
    #date_str = now.strftime("%Y-%m-%d_%H.%M.%S")

    #file_str = "psc_calibration_temp_" + SN + ".doc"
    file_str = "psc_calibration_temp.doc"
    fp = open(file_str, "w")
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
        _num_chan = dut.num_channels

        #turn all channels off
        caput(_psc+'1:DigOut_ON1-SP', 0)
        caput(_psc+'2:DigOut_ON1-SP', 0)
        caput(_psc+'3:DigOut_ON1-SP', 0)
        caput(_psc+'4:DigOut_ON1-SP', 0)
        print("Turning all channels off...")

        #put all ATE channels in test mode
        for x in ['1', '2', '3', '4']:
            sock.sendto(b'T' + x.encode('UTF-8') + b'0' + b'\n', server_address)
            time.sleep(0.5)

        #turn calibration source off
        sock.sendto(b'CAL0\n', server_address)
        time.sleep(1)

        #get dmm zero reading
        dmm_offs = float(get_dmm().decode('utf-8')) # reference current i0
        print(f"DMM zero offset reading: {dmm_offs:.7f}")

        #set channel j to cal mode
        #sock.sendto(b'T' + str(chan_index+1).encode('UTF-8') + b'1' + b'\n', server_address)
        sock.sendto(b'T' + physical_chan.encode('UTF-8') + b'1' + b'\n', server_address)
        time.sleep(0.5)

        #turn on cal source
        sock.sendto(b'CAL1\n', server_address)
        time.sleep(1)

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
            x = ser1.write(b"RANGE 1.0\n")
        if abs(current_high_ref) <= 0.11:
            x = ser1.write(b"RANGE 0.1\n")

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
            y0 = measure_testpoints(current_low_ref, sp0, 0, 0) # [dmm dac adc1 adc2 adc3 err]
            print_testpoints(y0,'v')
            if k==num_runs-1:
                fprint_testpoints(y0,'v')

            #print("")
            #print("Measuring i1")
            y1 = measure_testpoints(current_high_ref, sp1, 0, 0) # [dmm dac adc1 adc2 adc3 err]
            #print("   I      dacSP      dcct1      dcct2      dacRB      err")
            print_testpoints(y1,'')
            if k==num_runs-1:
                fprint_testpoints(y1,'')

            #Initial measured gains/offsets
            [mdac, m1, m2, m3, bdac, b1, b2, b3] = compute_m_b(y0, y1)

            print("")
            print(f"{'dacSP':>40}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}")
            print(f"{'Initial measured offsets: '}{bdac:>14.6f}{b1:>14.6f}{b2:>14.6f}{0:>14.6f}") #initial measured offsets
            print(f"{'Initial measured gains:   '}{mdac:>14.6f}{m1:>14.6f}{m2:>14.6f}{m3:>14.6f}") #initial measured gains
            print(f"{'Gain corrections:         '}{mdac:>14.6f}{1/m1:>14.6f}{1/m2:>14.6f}{1:>14.6f}")
            #print initial measured gain errors in percent (gtarget-m1)/gtarget*100, (gtarget-m2)/gtarget*100 ...

            print("")
            print("Writing gain and offset corrections for dacSP, dcct1, and dcct2 to PSC")

            if k==num_runs-1:
                fp.write("\n")
                fp.write(f"{'dacSP':>40}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
                fp.write(f"{'Initial measured offsets: '}{bdac:>14.6f}{b1:>14.6f}{b2:>14.6f}{0:>14.6f}\n") #initial measured offsets
                fp.write(f"{'Initial measured gains:   '}{mdac:>14.6f}{m1:>14.6f}{m2:>14.6f}{m3:>14.6f}\n") #initial measured gains
                fp.write(f"{'Gain corrections:         '}{mdac:>14.6f}{1/m1:>14.6f}{1/m2:>14.6f}{1:>14.6f}\n")
                #print initial measured gain errors in percent (gtarget-m1)/gtarget*100, (gtarget-m2)/gtarget*100 ...

                fp.write("\n")
                fp.write("Writing gain and offset corrections for dacSP, dcct1, and dcct2 to PSC\n")


            time.sleep(2)
            # offset constants are subtracted from ADC readings and DAC setpoint
            # write m1, m2, mdac, b1, b2, bdac to PSC (do not write m3, b3)
            caput(f'{_psc}{physical_chan}:DCCT1-Gain-SP', 1/m1)
            caput(f'{_psc}{physical_chan}:DCCT2-Gain-SP', 1/m2)
            caput(f'{_psc}{physical_chan}:DACSetPt-Gain-SP', mdac)
            caput(f'{_psc}{physical_chan}:DCCT1-Offset-SP', b1)
            caput(f'{_psc}{physical_chan}:DCCT2-Offset-SP', b2)
            caput(f'{_psc}{physical_chan}:DACSetPt-Offset-SP', bdac)

            print("")
            print("Measuring DAC readback gain and offset")
            #print("Measuring sp0")
            # #DAC readback corrections
            caput(f'{_psc}{physical_chan}:DAC_SetPt-SP', sp0)
            time.sleep(1)
            adc3 = caget(f'{_psc}{physical_chan}:DAC-I')
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
            caput(f'{_psc}{physical_chan}:DAC_SetPt-SP', sp1)
            time.sleep(1)
            adc3 = caget(f'{_psc}{physical_chan}:DAC-I')
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
            caput(f'{_psc}{physical_chan}:DAC-Gain-SP', 1/m3)
            caput(f'{_psc}{physical_chan}:DAC-Offset-SP', b3)

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
            y0 = measure_testpoints(current_low_ref, sp0, 0, 1) # [dmm dac adc1 adc2 adc3 err]
            print_testpoints(y0,'v')
            if k==num_runs-1:
                fprint_testpoints(y0,'v')

            y1 = measure_testpoints(current_high_ref, sp1, 0, 1) # [dmm dac adc1 adc2 adc3 err]
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
            #print initial measured gain errors in percent (gtarget-m1)/gtarget*100, (gtarget-m2)/gtarget*100 ...
            print("\n\n")

            if k==num_runs-1:
                fp.write("\n")
                fp.write("\n")
                fp.write(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
                fp.write(f"{'Final measured offsets: '}{bdac:>14.6f}{b1:>14.6f}{b2:>14.6f}{b3:>14.6f}\n")
                fp.write(f"{'Final measured gains:   '}{mdac:>14.6f}{m1:>14.6f}{m2:>14.6f}{m3:>14.6f}\n")
                #fp.write initial measured gain errors in percent (gtarget-m1)/gtarget*100, (gtarget-m2)/gtarget*100 ...
                fp.write("\n\n")

            cal_results[k,:] = [mdac, m1, m2, m3, bdac, b1, b2, b3]


        #np.set_printoptions(precision=6, suppress=True)

        m_avg = np.mean(cal_results, axis=0) # 0 is mean of each column. 1 is mean of each row
        m_std = np.std(cal_results, axis=0)
        print("")
        print("")
        print("")
        print(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}")
        print(f"{'Final meas. offsets mean: '}{m_avg[4]:>9.6f}{m_avg[5]:>14.6f}{m_avg[6]:>14.6f}{m_avg[7]:>14.6f}")
        print(f"{'Final meas. offsets stdev:'}{m_std[4]:>9.6f}{m_std[5]:>14.6f}{m_std[6]:>14.6f}{m_std[7]:>14.6f}")
        print(f"{'Final meas. gains mean:   '}{m_avg[0]:>9.6f}{m_avg[1]:>14.6f}{m_avg[2]:>14.6f}{m_avg[3]:>14.6f}")
        print(f"{'Final meas. gains stdev:  '}{m_std[0]:>9.6f}{m_std[1]:>14.6f}{m_std[2]:>14.6f}{m_std[3]:>14.6f}")
        print("")

        #if k==num_runs-1:
        fp.write("\n")
        fp.write(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
        fp.write(f"{'Final measured offsets mean: '}{m_avg[4]:>9.6f}{m_avg[5]:>14.6f}{m_avg[6]:>14.6f}{m_avg[7]:>14.6f}\n")
        fp.write(f"{'Final measured offsets stdev:'}{m_std[4]:>9.6f}{m_std[5]:>14.6f}{m_std[6]:>14.6f}{m_std[7]:>14.6f}\n")
        fp.write(f"{'Final measured gains mean:   '}{m_avg[0]:>9.6f}{m_avg[1]:>14.6f}{m_avg[2]:>14.6f}{m_avg[3]:>14.6f}\n")
        fp.write(f"{'Final measured gains stdev:  '}{m_std[0]:>9.6f}{m_std[1]:>14.6f}{m_std[2]:>14.6f}{m_std[3]:>14.6f}\n")
        fp.write("\n")

        print(f"Saving channel {physical_chan} calibration data to qspi\n")
        fp.write(f"Saving channel {physical_chan} calibration constants to qspi\n")
        if chan_index>0:
            fp.write("\n\n\n\n\n")
        if chan_index==(dut.num_channels-1):
            fp.write("Test data reviewed by ______________________________   Date_____________")
        fp.write("\n\n")
        fp.write(f"\nPage {chan_index+1} of {dut.num_channels}")
        caput(f'{_psc}{physical_chan}:WriteQspi-SP', 1) # write all data to qspi

        if chan_index<3:
            #fp.write("\r\n") # form feed aka page break
            fp.write("\f") # form feed aka page break

    print("Calibration complete.")


    fp.close()

    #turn calibration source off
    set_atsdac_cal_source(0)
    time.sleep(0.1)
    sock.sendto(b'CAL0\n', server_address)
    #put all ATE channels in test mode
    for x in ['1', '2', '3', '4']:
        sock.sendto(b'T' + x.encode('UTF-8') + b'0' + b'\n', server_address)
        time.sleep(0.5)

    file_str1 = os.path.join(dut.cal_report_dir, f"{designation}{dut.psc_sn}_{dut.dir_timestamp}")
    os.system(f'cp "{file_str}" "{file_str1}.doc"')


if __name__ == "__main__":
    local_dut = DUT()
    local_dut.prompt_inputs()
    run_calibration(local_dut)

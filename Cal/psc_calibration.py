import time
import sys
import socket
import os
import datetime
import numpy as np
from epics import caget, caput
import serial

# pylint: disable=wrong-import-position
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


ATE_IP_ADDRESS = '10.69.26.3'


def run_calibration(dut: DUT):
    """Executes the calibration routine, but now using the DUT parameters
    instead of hard-coding"""

    now=datetime.datetime.now()
    formatted_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
    formatted_date = now.strftime("%Y-%m-%d")

    psc = f"lab{{{dut.psc_num}}}Chan"

    num_chan = len(dut.model.channels)
    designation = dut.model.designation
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

    string1 = "Calibrating PSC model " + designation + "SN" + dut.psc_sn
    print(string1)

    N=5 # of runs per channel

    ser1 = serial.Serial('/dev/ttyUSB0', 115200, timeout=30)
    x = ser1.write(b"++addr 24\n")
    x = ser1.write(b"++auto 0\n")
    x = ser1.write(b"AZERO ON\n")
    x = ser1.write(b"NPLC 30\n")

    IP = ATE_IP_ADDRESS
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        server_address = (IP, 5000)
        #sock.bind (server_address)
    except Exception as err:
        print("Socket error: %s" % err)





    #print("Target gain = %f (V/A)" % gtarget)

    # b1 = dcct1 adc1 offset
    # b2 = dcct2 adc2offset
    # b3 = dac rdbk adc3 offset
    # bdac = dac sp offset | err=0

    # m1 = dcct1 adc1 gain
    # m2 = dcct2 adc2 gain
    # m3 = dac rdbk adc3 gain
    # mdac = dac sp gain | err=0


    def get_3458A():
        x = ser1.write("TARM SGL\n".encode('utf-8'))
        time.sleep(1)
        x = ser1.write(b"++auto 1\n")
        data = ser1.read_until(b'\n',1000)
        x = ser1.write(b"++auto 0\n")
        return data

    def set_atsdac_cal_source(Ival):
        y = str(Ival*50) # 50V/A
        sock.sendto(b'CALDAC' + y.encode('UTF-8') + b'\n', server_address)

    def measure_testpoints(I, sp, j, verbose, verification):
        #print("%3.6f" % I)
        #i0 = -Ifs*0.1 # unipolar
        #set_keithley2401(I)
        for i in range(4):
            set_atsdac_cal_source(I)
            time.sleep(0.5)
        adc1 = caget(psc+chan[j]+':DCCT1-I')
        #print(adc1)
        #print(I*Ndcct)
        time.sleep(1)
        if (abs(adc1)-abs(I*Ndcct)) > 0.3*abs(I*Ndcct):
            print("Error setting calibration DAC setpoint. Try again.")
            sys.exit()
        #time.sleep(5)
        if verbose:
            print("Adjusting DAC for null error")
        #td = [2, 2, 2] # wait time after changing DAC
        td=2
        #err=0
        i=0
        caput(psc+chan[j]+':DAC_SetPt-SP', sp)    # set DAC
        time.sleep(td)
        err = caget(psc+chan[j]+':Error-I') # get err
        #for i in range(3):
        # choose Ifs*2 as max allowable value of error for null. i==0 condition ensures that loop runs once.
        while abs(err)>Ifs*2 and i<12 or i==0:
            #if verbose:
            if(True):
                print("adjustment %d" % i)
            #caput(psc+chan[j]+':SF:AmpsperSec-SP', R[i]) #set ramp rate
            #time.sleep(td[i])
            dac = sp - err/400*G
            sp = dac
            caput(psc+chan[j]+':DAC_SetPt-SP', sp)    # set DAC
            time.sleep(td)
            err = caget(psc+chan[j]+':Error-I') # get err
            i+=1
            #print(i)
        if i == 12:
            print("Calibration failed. Could not null error. Try again.")
            sys.exit()

        i=0
        x=0
        if verification==0:
            while(i<4 and x==0):
                adc1 = caget(psc+chan[j]+':DCCT1-I')
                adc2 = caget(psc+chan[j]+':DCCT2-I')
                adc3 = caget(psc+chan[j]+':DAC-I')
                dmm = float(get_3458A().decode('utf-8')) - dmm_offs  # reference current i0
                i+=1
                if abs(adc1+sp) < 0.02*Ifs*Ndcct and abs(adc2+sp) < 0.02*Ifs*Ndcct and \
                abs(adc3-sp) < 0.02*Ifs*Ndcct and abs(dmm*gtarget*G+sp) < 0.02*Ifs*Ndcct:
                    x=1 # if all readings good, break loop
                time.sleep(1)
            if i == 4:
                print("adc1 = %3.5f" % adc1)
                print("adc2 = %3.5f" % adc2)
                print("adc3 = %3.5f" % adc3)
                print("sp = %3.5f" % sp)
                dmm_scaled = dmm*gtarget*G
                print("dmm = %3.5f" % dmm_scaled)
                print("Calibration failed. Bad initial measurement(s). Try again.")
                sys.exit()

        if verification==1:
            while(i<4 and x==0):
                adc1 = caget(psc+chan[j]+':DCCT1-I')
                adc2 = caget(psc+chan[j]+':DCCT2-I')
                adc3 = caget(psc+chan[j]+':DAC-I')
                dmm = float(get_3458A().decode('utf-8')) - dmm_offs # reference current i0
                i+=1
                if abs(adc1+sp) < 0.0002*Ifs*Ndcct and abs(adc2+sp) < 0.0002*Ifs*Ndcct and \
                abs(adc3-sp) < 0.0002*Ifs*Ndcct and abs(dmm*gtarget*G+sp) < 0.0002*Ifs*Ndcct:
                    x=1 # if all readings good, break loop
                time.sleep(1)
            if i == 4:
                print("adc1 = %3.5f" % adc1)
                print("adc2 = %3.5f" % adc2)
                print("adc3 = %3.5f" % adc3)
                print("sp = %3.5f" % sp)
                print("Calibration failed. Bad verification measurement(s). Try again.")
                sys.exit()




        #caput(psc+chan[j]+':SF:AmpsperSec-SP', 10)
        #time.sleep(1)

        return [dmm*gtarget*G, dac, adc1, adc2, adc3, err]


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
        if(v=='v'):
            print(f"{'Itest':>14}{'dacSP':>14}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}{'err':>14}")
        print(f"{y[0]:>14.6f}{y[1]:>14.6f}{y[2]:>14.6f}{y[3]:>14.6f}{y[4]:>14.6f}{y[5]:>14.6f}")

    def fprint_testpoints(y, v):
        if(v=='v'):
            fp.write(f"{'Itest':>12}{'dacSP':>12}{'dcct1':>12}{'dcct2':>12}{'dacRB':>12}{'err':>12}\n")
        fp.write(f"{y[0]:>12.6f}{y[1]:>12.6f}{y[2]:>12.6f}{y[3]:>12.6f}{y[4]:>12.6f}{y[5]:>12.6f}\n")


    #now = datetime.now()
    #date_str = now.strftime("%Y-%m-%d_%H.%M.%S")
    
    #file_str = "psc_calibration_temp_" + SN + ".doc"
    file_str = "psc_calibration_temp.doc"
    fp = open(file_str, "w")
    fp.write("Report of Calibration\n")
    fp.write("PSC %sS/N %s\n" % (designation, dut.psc_sn))
    fp.write(formatted_date_time+"\n\n")
    #fp.write("Calibration Current standard: Keithley 2401\n")
    fp.write("Calibration Current standard: BNL PSC ATE S/N 001\n")
    #fp.write("Calibration Volt standard: HP 3458A-002 S/N 2823A 06900\n")
    fp.write("Calibration Volt standard: HP 3458A-002 S/N 2823A 23647\n")
    fp.write("Calibration Resistance standard: Fluke 742A-1 S/N 1063008\n")
    fp.write("End Header\n\n\n")

    for j in range(len(chan)): # loop through channels

        #turn all channels off
        caput(psc+'1:DigOut_ON1-SP', 0)
        caput(psc+'2:DigOut_ON1-SP', 0)
        caput(psc+'3:DigOut_ON1-SP', 0)
        caput(psc+'4:DigOut_ON1-SP', 0)
        print("Turning all channels off...")
    
        #put all ATE channels in test mode
        for x in ['1', '2', '3', '4']:
            sock.sendto(b'T' + x.encode('UTF-8') + b'0' + b'\n', server_address)
            time.sleep(0.5)

        #turn calibration source off
        sock.sendto(b'CAL0\n', server_address)
        time.sleep(1)

        #get dmm zero reading
        dmm_offs = float(get_3458A().decode('utf-8')) # reference current i0
        print("DMM zero offset reading: %1.7f" % dmm_offs)
        
        #set channel j to cal mode
        #sock.sendto(b'T' + str(j+1).encode('UTF-8') + b'1' + b'\n', server_address)
        sock.sendto(b'T' + chan[j].encode('UTF-8') + b'1' + b'\n', server_address)
        time.sleep(0.5)

        #turn on cal source
        sock.sendto(b'CAL1\n', server_address)
        time.sleep(1)

        gtarget = Rb[j]*10.0 # V/A
        G = Ndcct/gtarget # power supply scale factor A/V
        #G=1.0
        Ifs = 1.0/Rb[j] # max burden current
        #print(Ifs)
        I0 = -1.0/Ndcct # 1 A
        sp0 = 1.0
        I1 = -(float(round(Ifs*0.9*1000)/1000)) # round to nearest mA
        #sp1 = float(int(10*G*0.9)) #  must be close to current setting to keep error from saturating
        sp1 = float(round(10*G*0.9))
        #print("%3.6f   %.6f   %3.6f   %3.6f" % (sp0, sp1, I0, I1))
        y0 = np.zeros(6) # readbacks
        y1 = np.zeros(6)
        M = np.zeros((N,8)) # gains/offsets multiple runs
        if abs(I1) > 0.11:
            x = ser1.write(b"RANGE 1.0\n")
        if abs(I1) <= 0.11:
            x = ser1.write(b"RANGE 0.1\n")

        print(psc+chan[j])
        print("Burden resistor = %3.4f" % Rb[j])

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


        for k in range(N): # N runs on each channel
            print("")
            print("Run #: %d" % (k+1) )
            #CHx
            #Calibration


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



            print("Measuring initial gains and offsets")
            if k==N-1:
                fp.write(psc+chan[j]+"\n")
                fp.write("Burden resistor = %3.4f\n\n" % Rb[j])
                fp.write("Measuring initial gains and offsets\n")
            #print("Measuring i0")
            y0 = measure_testpoints(I0, sp0, j, 0, 0) # [dmm dac adc1 adc2 adc3 err]
            print_testpoints(y0,'v')
            if k==N-1:
                fprint_testpoints(y0,'v')

            #print("")
            #print("Measuring i1")
            y1 = measure_testpoints(I1, sp1, j, 0, 0) # [dmm dac adc1 adc2 adc3 err]
            #print("   I      dacSP      dcct1      dcct2      dacRB      err")
            print_testpoints(y1,'')
            if k==N-1:
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

            if k==N-1:
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
            caput(psc+chan[j]+':DCCT1-Gain-SP', 1/m1)
            caput(psc+chan[j]+':DCCT2-Gain-SP', 1/m2)
            caput(psc+chan[j]+':DACSetPt-Gain-SP', mdac)
            caput(psc+chan[j]+':DCCT1-Offset-SP', b1)
            caput(psc+chan[j]+':DCCT2-Offset-SP', b2)
            caput(psc+chan[j]+':DACSetPt-Offset-SP', bdac)

            print("")
            print("Measuring DAC readback gain and offset")
            #print("Measuring sp0")
            # #DAC readback corrections
            caput(psc+chan[j]+':DAC_SetPt-SP', sp0)
            time.sleep(1)
            adc3 = caget(psc+chan[j]+':DAC-I')
            y0[4] = adc3
            print("DAC SP   DAC RB")
            print("%2.6f   %2.6f " % (sp0, y0[4]))

            if k==N-1:
                fp.write("\n")
                fp.write("Measuring DAC readback gain and offset\n")
                #fp.write("Measuring sp0\n")
                fp.write("DAC SP   DAC RB\n")
                fp.write("%2.6f   %2.6f \n" % (sp0, y0[4]))

            #print("Measuring sp1")
            caput(psc+chan[j]+':DAC_SetPt-SP', sp1)
            time.sleep(1)
            adc3 = caget(psc+chan[j]+':DAC-I')
            y1[4] = adc3
            print("%2.6f   %2.6f " % (sp1, y1[4]), end="")
            print("")
            if k==N-1:
                fp.write("%2.6f   %2.6f \n" % (sp1, y1[4]))

            m3 = (y1[4]-y0[4])/(sp1-sp0)
            b3 = y0[4]-m3*sp0

            print("Measured offset: %f" % (b3) ) #initial measured offsets
            print("Measured gain: %f" % (m3) ) #initial measured gains
            print("Gain correction: %f" % (1/m3) )

            print("")
            print("Writing gain and offset constants for dacRB to PSC")
            time.sleep(2)
            # write m3, b3 to PSC
            caput(psc+chan[j]+':DAC-Gain-SP', 1/m3)
            caput(psc+chan[j]+':DAC-Offset-SP', b3)

            if k==N-1:
                fp.write("\n")
                fp.write("Measured offset: %f\n" % (b3) ) #initial measured offsets
                fp.write("Measured gain: %f\n" % (m3) ) #initial measured gains
                fp.write("Gain correction: %f\n" % (1/m3) )
                fp.write("\n")
                fp.write("Writing gain and offset constants for dacRB to PSC\n\n")


            # Verification
            print("\n\n")
            print("Verification")
            if k==N-1:
                fp.write("Verification\n")
            y0 = measure_testpoints(I0, sp0, j, 0, 1) # [dmm dac adc1 adc2 adc3 err]
            print_testpoints(y0,'v')
            if k==N-1:
                fprint_testpoints(y0,'v')

            y1 = measure_testpoints(I1, sp1, j, 0, 1) # [dmm dac adc1 adc2 adc3 err]
            print_testpoints(y1,'')
            if k==N-1:
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

            if k==N-1:
                fp.write("\n")
                fp.write("\n")
                fp.write(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
                fp.write(f"{'Final measured offsets: '}{bdac:>14.6f}{b1:>14.6f}{b2:>14.6f}{b3:>14.6f}\n")
                fp.write(f"{'Final measured gains:   '}{mdac:>14.6f}{m1:>14.6f}{m2:>14.6f}{m3:>14.6f}\n")
                #fp.write initial measured gain errors in percent (gtarget-m1)/gtarget*100, (gtarget-m2)/gtarget*100 ...
                fp.write("\n\n")

            M[k,:] = [mdac, m1, m2, m3, bdac, b1, b2, b3]


        #np.set_printoptions(precision=6, suppress=True)

        Mavg = np.mean(M, axis=0) # 0 is mean of each column. 1 is mean of each row
        Mstd = np.std(M, axis=0)
        print("")
        print("")
        print("")
        print(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}")
        print(f"{'Final meas. offsets mean: '}{Mavg[4]:>9.6f}{Mavg[5]:>14.6f}{Mavg[6]:>14.6f}{Mavg[7]:>14.6f}")
        print(f"{'Final meas. offsets stdev:'}{Mstd[4]:>9.6f}{Mstd[5]:>14.6f}{Mstd[6]:>14.6f}{Mstd[7]:>14.6f}")
        print(f"{'Final meas. gains mean:   '}{Mavg[0]:>9.6f}{Mavg[1]:>14.6f}{Mavg[2]:>14.6f}{Mavg[3]:>14.6f}")
        print(f"{'Final meas. gains stdev:  '}{Mstd[0]:>9.6f}{Mstd[1]:>14.6f}{Mstd[2]:>14.6f}{Mstd[3]:>14.6f}")


        #print initial measured gain errors in percent (gtarget-m1)/gtarget*100, (gtarget-m2)/gtarget*100 ...
        print("")

        #if k==N-1:
        fp.write("\n")
        fp.write(f"{'dacSP':>38}{'dcct1':>14}{'dcct2':>14}{'dacRB':>14}\n")
        fp.write(f"{'Final measured offsets mean: '}{Mavg[4]:>9.6f}{Mavg[5]:>14.6f}{Mavg[6]:>14.6f}{Mavg[7]:>14.6f}\n")
        fp.write(f"{'Final measured offsets stdev:'}{Mstd[4]:>9.6f}{Mstd[5]:>14.6f}{Mstd[6]:>14.6f}{Mstd[7]:>14.6f}\n")
        fp.write(f"{'Final measured gains mean:   '}{Mavg[0]:>9.6f}{Mavg[1]:>14.6f}{Mavg[2]:>14.6f}{Mavg[3]:>14.6f}\n")
        fp.write(f"{'Final measured gains stdev:  '}{Mstd[0]:>9.6f}{Mstd[1]:>14.6f}{Mstd[2]:>14.6f}{Mstd[3]:>14.6f}\n")
        fp.write("\n")

        print("Saving channel %s calibration data to qspi\n" % (chan[j]))
        fp.write("Saving channel %s calibration constants to qspi\n" % (chan[j]))
        if j>0:
            fp.write("\n\n\n\n\n")
        if j==(len(chan)-1):
            fp.write("Test data reviewed by ______________________________   Date_____________")
        fp.write("\n\n")
        fp.write("\nPage %d of %d" % ((j+1), len(chan)))
        caput(psc+chan[j]+':WriteQspi-SP', 1) # write all data to qspi

        if j<3:
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

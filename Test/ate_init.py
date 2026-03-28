"""ATE Initializtion Submodule
Modified M. Capotosto 11-9-2025
Original: T. Caracappa
"""

from time import sleep
from Common.EPICS_Adapters.ate_epics import ATE
from Common.initialize_dut import DUT


def ate_init(ate: ATE, dut: DUT) -> None:
    """
    Initializes the ATE and applies default safety settings for
    all DUT channels.

    Iterates through each channel of the Device Under Test (DUT) to perform a
    standard initialization sequence:
      - Disables DCCT fault channels.
      - Resets Ignd (Ground Current) to 0.
      - Sets mode to TEST (0) and applies default gains (Vmon=0.5, Imon=0.25).
      - Syncs polarity with the hardware state.
      - Disables calibration mode and resets the calibration DAC.
      - Clears PC faults.

    Args:
        ate: The ATE interface instance used to control the tester hardware.
        dut: The Device Under Test instance containing configuration (e.g.,
             num_channels) and the PSC interface.

    Raises:
        AssertionError: If the DUT does not have a valid PSC interface.
    """
    assert dut.psc is not None
    print("#########################################\n"
          "# **********Initializing ATE...**********\n"
          "#########################################\n")
    for ch in dut.model.channels:
        print(f"Initializing ATE, Ch{ch}")
        ate.set_dcct_fault_channel(0)
        ate.set_ignd_channel(ch)
        ate.set_ignd_value(0, ch, dut)
        ate.set_mode(ch, 0)
        ate.set_vmon_gain(ch, 0.5)
        ate.set_imon_gain(ch, 0.25)
        print("Initialized DCCT, IGND, Mode, VMON, IMON...")
        ate.set_polarity(dut.psc.get_polarity())
        # ate.set_polarity(0)
        ate.set_cal_state(0)
        ate.set_cal_dac(0)
        print("Initialize Polarity Mode, Cal State, Cal DAC...")
        ate.set_pc_fault(ch, 0)
        sleep(4)
        print("Initialize PC Fault...")
    sleep(1)
    print("ATE is Initialized...")

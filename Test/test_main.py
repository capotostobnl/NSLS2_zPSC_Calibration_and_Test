"""Main module for PSC Testing.

M. Capotosto 11/11/2025
"""

import os
import sys
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
import subprocess
from Common.EPICS_Adapters.ate_epics import ATE
from Common.initialize_dut import DUT
from Test.test_report_generator import start_report, finalize_report, \
    channel_section
from Test.ate_init import ate_init
from Test.Functional_Tests.evr_timing_test import evr_timing_test
from Test.Functional_Tests.ate_fault_tests import ate_fault_tests
from Test.Functional_Tests.ps_regulation_test import ps_regulation_test
from Test.Functional_Tests.jump_test import jump_test
from Test.Functional_Tests.smooth_ramp_test import smooth_ramp_test
from Test.Functional_Tests.fofb_test import \
    fofb_daisy_packet_monotonic_test


def run_psc_test_suite(dut_instance=None):
    """
    Runs the full PSC test suite.

    Args:
        dut_instance (DUT, optional): A pre-configured DUT object.
                                      If None, the script will prompt the user.
    """
    ate = ATE(prefix="PSCtest:", ch_fmt="CH{ch}:")

    # ##############################################################
    # Setup DUT (Device Under Test)
    # ##############################################################
    if dut_instance is None:
        print("--- Running in Standalone Mode ---")
        dut = DUT()
        dut.prompt_inputs()
    else:
        # CASE 2: LAUNCHER MODE
        # The launcher passed us a DUT object ready to go.
        dut = dut_instance

    # Initialize hardware connection 
    dut.init()

    ctx, pdf_path = start_report(dut)


    evr_timing_test(dut, ctx)
    ate_init(ate, dut)

    for chan, drive, readback in zip(dut.model.channels,
                                     dut.model.drive_channels,
                                     dut.model.readback_channels
                                     ):
    
#    for chan, drive, readback in zip((3, 4), (3, 4), (3, 4)):
        with channel_section(ctx, chan) as sec:
            print("\n\n*******************************************"
                  f"\nBeginning Channel {chan} ATE Fault Tests..."
                  "\n*******************************************")
            ate_fault_tests(dut, ate, sec, chan)

            if dut.model.func_tests.is_enabled("regulation", chan):
                print("\n\n*******************************************"
                    f"\nBeginning Channel {chan} Regulation Tests..."
                    "\n*******************************************")
                ps_regulation_test(dut, ate, sec, chan, ctx, drive, readback)

            if dut.model.func_tests.is_enabled("jump", chan):
                print("\n\n*******************************************"
                    f"\nBeginning Channel {chan} Jump Tests..."
                    "\n*******************************************")
                jump_test(dut, ate, sec, chan, ctx, drive, readback)

            if dut.model.func_tests.is_enabled("smooth", chan):
                print("\n\n*******************************************"
                    f"\nBeginning Channel {chan} Smooth Ramp Tests..."
                    "\n*******************************************")
                smooth_ramp_test(dut, ate, sec, chan, ctx, drive, readback)

    print(dut.bandwidth)
    if dut.bandwidth == "F":
        print("\n\n*******************************************"
              "\nBeginning FOFB Tests..."
              "\n************************************* ******")
        fofb_daisy_packet_monotonic_test(dut, ctx)

    finalize_report(ctx)
    print(f"Test complete! See folder for report: {pdf_path}")
    
    try:
        if os.environ.get("DISPLAY"):
            subprocess.Popen(["xdg-open", pdf_path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            print("No DISPLAY found (headless/SSH). Not opening PDF automatically.")
    except Exception as e:
        print(f"Could not auto-open PDF: {e}")


if __name__ == "__main__":
    run_psc_test_suite(dut_instance=None)

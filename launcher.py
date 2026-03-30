"""
PSC Automation Suite Launcher
=============================

This module serves as the primary entry point for the ALSU-PSC Calibration
and Functional Test Suite. It coordinates the high-level execution flow
by managing shared session state and user configuration.

The launcher facilitates:
- **Execution Mode Selection**: Allows operators to run calibration,
  functional testing, or both in a single session.
- **Session Management**: Initializes a shared `DUT` (Device Under Test)
  instance to anchor project paths and perform hardware discovery.
- **Dependency Injection**: Captures hardware identifiers and model
  specifications once, passing them into downstream sub-suites to
  prevent redundant user prompts.

Workflow:
    1. Prompt user for execution mode (Cal/Test/Both).
    2. Initialize `DUT` object to resolve project-relative paths.
    3. Prompt for shipment/hardware identifiers via `dut.prompt_inputs()`.
    4. If Calibration is selected, retrieve the specific `PSCModel`
       configuration.
    5. Execute selected suites using the shared `DUT` and `config_instance`.
"""
import sys
import os
import time
import subprocess
from Test.test_main import run_psc_test_suite
from Cal.psc_calibration import run_calibration
from Common.initialize_dut import DUT


def prompt_execution_mode():
    """
    Prompts the user to select an execution mode.
    Guards against invalid inputs.

    Returns:
        str: The selected mode ('cal_only', 'test_only', or 'cal_and_test')
    """

    while True:
        print("\n--------------------------------")
        print("Select Execution Mode:")
        print("1. Calibrate Only")
        print("2. Test Only")
        print("3. Calibrate and Test")
        print("--------------------------------")

        selection = str(input("\nEnter selection (1-3): ").strip())

        if selection == "1":  # Cal Only
            cal_sel = True
            test_sel = False
            return cal_sel, test_sel
        elif selection == "2":  # Test Only
            cal_sel = False
            test_sel = True
            return cal_sel, test_sel
        elif selection == "3":  # Cal and Test
            cal_sel = True
            test_sel = True
            return cal_sel, test_sel
        else:
            print(
                f"\n[!] Invalid input: '{selection}'. \n"
                "Please enter 1, 2, or 3."
                )


def sleep_func(sleep_time):
    """Delay/Sleep function to delay prior to beginning cal and/or test,
    to allow for unattended testing with unit warm up time prior to
    execution"""

    print(f"Sleeping {sleep_time} Minutes")

    total_seconds = sleep_time * 60
    print(f"Minutes remaining: {total_seconds/60}")
    while total_seconds >= 0:
        mins = total_seconds // 60
        secs = total_seconds % 60

        timer_display = f"{mins:02d}:{secs:02d}"

        print(f"Time remaining: {timer_display}")

        time.sleep(1)
        total_seconds -= 1


def main():
    """
    Coordinates the primary execution flow for the PSC automation suite.

    This function serves as the central orchestrator for the application
    session. It performs the following sequence:
    1.  Prompts the operator to select the execution mode (Calibration,
        Functional Testing, or both).
    2.  Instantiates the shared DUT (Device Under Test) object, which
        anchors project-relative file paths and queries hardware
        configuration via EPICS.
    3.  Collects operator inputs and discovery data once to establish
        a single source of truth for the session.
    4.  Injects the shared DUT and PSCModel configuration into the
        selected sub-suites (Calibration and/or Testing) to ensure
        data consistency and eliminate redundant prompts.
    """
    cal, test = prompt_execution_mode()

    dut = DUT()
    dut.prompt_inputs()
    sleep_time = 0
    sleep_time = int(input("How long do you want to sleep before beginning? "
                           "(Minutes): "))

    sleep_func(sleep_time)

    if cal:
        while True:
            autocal = input("Have you run the DMM Self-Calibration within the "
                            "last 8 hours? <Y/N>")
            if autocal in ('Y', 'y'):
                break
            elif autocal in ('N', 'n'):
                input("Please run AutoCal for DCV Range!\n\n"
                      "Press return when DMM is done, to launch"
                      " calibration...")
                break
            else:
                print("Invalid input. Please enter <Y/N>")
        print("Starting Calibration script subprocess...\n\n\n")
        print("----------------------------------------------------------\n\n")
        """
        # OS indiscriminate/Path safe jump to subdir for cal script
        launcher_dir = os.path.dirname(os.path.abspath(__file__))
        target_script = os.path.join(launcher_dir, 'Cal', 'psc_calibration.py')

        try:
            # sys.executable runs the same Python interpreter used
            # for Launcher.py...
            # check=True Raise exception if subprocess returns
            # non-zero exit code

            subprocess.run([sys.executable, target_script], check=True)
        except subprocess.CalledProcessError as e:
            print("\nThe calibration script crashed or was cancelled "
                  f"(Return code: {e.returncode})")
            cal_returncode = e.returncode
        """
        run_calibration(dut=dut)


        print("----------------------------------------------------------\n\n")
        if test:
            if cal_returncode:
                input("Cal failed! Press return to continue...") 
            elif not cal_returncode:
                print("Calibration complete. Continuing to functional test...\n\n")
        else:
            if cal_returncode:
                print("Calibration failed! Exiting...")
                sys.exit()
            elif not cal_returncode:
                print("Calibration complete. Exiting!")
                sys.exit()

    if test:
        print("Beginning functional test...")
        run_psc_test_suite(dut)


if __name__ == "__main__":
    main()

"""
ATE Fault Test Submodule

This module executes automated fault testing for Power Supply
Controllers (PSC). It interfaces with the Automated Test Equipment
(ATE) to inject specific hardware faults (e.g., Interlocks,
DCCT faults) and verifies that the PSC correctly detects and latches
these faults via boolean bit evaluation helper functions.

Modified: M. Capotosto 5/20/2026
"""

from __future__ import annotations
import os, sys
import subprocess
import threading
import time
from queue import Queue, Empty
from typing import Any

from reportlab.lib.units import inch
from reportlab.platypus import Table, Spacer
from reportlab.lib import colors

# flake8: noqa: E402
# pylint: disable=wrong-import-position
###############################################################################
#   Add outer directory to path, so app can find common dir when run standalone
if __name__ == "__main__":

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(parent_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    if project_root not in sys.path:
        sys.path.append(project_root)
###############################################################################
from testing.test_report_generator import channel_section
from common.initialize_dut import DUT
from common.epics_adapters.ate_epics import ATE
from testing.test_report_generator import start_report, finalize_report


# =============================================================================
# camonitor helpers
# =============================================================================


class EpicsMonitor:
    """
    Context manager that spawns a 'camonitor' subprocess to watch a PV.
    Ensures the background process is killed strictly upon exit to prevent
    zombie processes.
    """
    def __init__(self, pvname: str):
        self.pvname = pvname
        self.process: subprocess.Popen | None = None
        self.queue: Queue = Queue()
        self.thread: threading.Thread | None = None
        self.last_known_value: int = 0
        self.running = False

    def _enqueue_output(self, pipe):
        try:
            for line in iter(pipe.readline, ""):
                self.queue.put(line)
        except (ValueError, OSError):
            pass
        finally:
            pipe.close()

    def __enter__(self):
        self.process = subprocess.Popen(
            ["camonitor", self.pvname],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            text=True,
            close_fds=True
        )
        self.running = True
        self.thread = threading.Thread(
            target=self._enqueue_output,
            args=(self.process.stdout,),
            daemon=True
        )
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.kill()
                self.process.wait(timeout=1)
            except (subprocess.TimeoutExpired, OSError):
                pass

            if self.process.stdout:
                self.process.stdout.close()
            if self.process.stderr:
                self.process.stderr.close()

    def get_latest(self) -> int:
        """"""
        latest_line = None
        while not self.queue.empty():
            try:
                latest_line = self.queue.get_nowait()
            except Empty:
                break

        if latest_line:
            try:
                val_str = latest_line.strip().split()[-1]
                self.last_known_value = int(val_str)
            except (ValueError, IndexError):
                pass

        return self.last_known_value


# =============================================================================
# Fault Configuration Table
# =============================================================================
# Format: (getter_method_name, label, setter_method_name, setter_bool)
FAULT_TESTS = [
    ("get_flt_1_bit", "#1",    "set_flt1", True),
    ("get_flt_2_bit", "#2",    "set_flt2", True),
    ("get_flt_3_bit", "SPARE", "set_fltspare", True),
]


def _run_single_fault_test(getter_name: str, label: str, setter: Any,
                           setter_bool: bool, dut: DUT, chan: int) -> \
                           tuple[str, int]:
    """
    Run ONE fault test sequence (Trigger -> Detect -> Clear) with retries.

    Args:
        getter_name (str): The name of the DUT function that checks the bit (returns bool).
        label (str): Human-readable name of the fault (e.g., "#1", "SPARE").
        setter (func): The ATE method used to inject the fault.
        setter_bool (bool): True if the setter takes (chan, bool), False if
                            it takes (chan) or (0).
        dut (DUT): Device Under Test interface.
        chan (int): The channel to test.

    Returns:
        tuple[str, int]: ("PASS"/"FAIL", ColorFlag). ColorFlag 0=Green, 1=Red.
    """

    # Dynamically extract the target bit evaluation helper from your DUT instance
    getter = getattr(dut.psc, getter_name)

    # -------------------------------------------------------------
    # Helper: run the "fault trigger + detection" portion once
    # -------------------------------------------------------------
    def run_detection_pass() -> bool:
        """
        Injects the fault via ATE and monitors the custom getter function.
        Returns True if the fault bit registers True.
        """
        # Prime the interface/hardware stability
        time.sleep(0.5)

        # Trigger the fault
        if setter_bool:
            setter(chan, True)
        else:
            setter(chan)

        set_command_time = time.time()
        detected = False

        # Watch for fault (timeout 10s)
        start_wait = time.time()
        while (time.time() - start_wait) < 10.0:
            # Fix: Pass the required 'chan' positional argument here
            if getter(chan):
                detected = True
                break

            time.sleep(0.05)

        # Ensure minimum dwell time after command (for hardware stability)
        elapsed = time.time() - set_command_time
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        return detected

    # -------------------------------------------------------------
    # Helper: Clearing Pass
    # -------------------------------------------------------------
    def run_clear_pass() -> bool:
        """
        Removes the ATE fault condition, resets the PSC, and verifies
        that the target fault bit has cleared.
        """
        # 1. Remove the ATE fault condition
        if setter_bool:
            setter(chan, False)
        else:
            setter(0)

        # Hardware soak
        time.sleep(4)

        # 2. Reset the PSC
        dut.psc.set_reset(chan, 1)
        time.sleep(1)
        dut.psc.clear_faults(chan, 1)
        time.sleep(1)
        dut.psc.set_reset(chan, 0)
        time.sleep(0.5)
        dut.psc.clear_faults(chan, 0)
        time.sleep(0.5)

        # 3. Verify the bit shows clear
        # Poll for up to 20 seconds (200 * 0.1s)
        for _ in range(200):
            # Fix: Pass the required 'chan' positional argument here too
            if not getter(chan):
                return True
            time.sleep(0.1)

        return False

    # -------------------------------------------------------------
    # PHASE 1: Detection retries (up to 3 times)
    # -------------------------------------------------------------
    detected_ok = False
    for attempt in range(1, 4):
        print(f"Attempt {attempt}/3: Fault {label} detection...")
        if run_detection_pass():
            detected_ok = True
            break
        print("Detection failed; retry in 3 seconds...")
        time.sleep(3)

    # -------------------------------------------------------------
    # PHASE 2: Clearing retries (up to 3 times)
    # -------------------------------------------------------------
    cleared_ok = False
    for attempt in range(1, 4):
        print(f"Attempt {attempt}/3: Fault {label} clearing...")
        if run_clear_pass():
            cleared_ok = True
            break
        print("Clear failed; retry in 3 seconds...")
        time.sleep(3)

    # -------------------------------------------------------------
    # FINAL RESULTS
    # -------------------------------------------------------------
    final_pass = detected_ok and cleared_ok
    result = "PASS" if final_pass else "FAIL"
    color = 0 if final_pass else 1
    return result, color

# =============================================================================
# Main Test Routine
# =============================================================================

def ate_fault_tests(dut: DUT, ate: ATE, section: list, chan: int):
    """
    Main driver for automated ATE Fault Testing using boolean bit evaluations.
    """
    assert dut.psc is not None

    print("==============================================")
    print("          ATE Fault Test Starting")
    print("==============================================")
    print(f"Channel: {chan}\n")

    # Basic PSC setup
    dut.psc.set_dac_setpt(chan, 0)
    time.sleep(0.5)
    dut.psc.set_power_on1(chan, 0)
    time.sleep(0.5)
    dut.psc.set_enable_on2(chan, 0)
    time.sleep(0.5)
    dut.psc.set_park(chan, 0)
    time.sleep(0.5)
    dut.psc.set_rate(chan, 4)
    time.sleep(0.5)

    # ATE setup
    ate.set_dcct_fault_channel(0)
    ate.set_ignd_channel(chan)
    ate.set_ignd_value(0.1, chan, dut)

    tdata = [[f"ATE Fault Tests for Channel {chan}", 0]]
    tcolor = []  # 0 for Green, 1 for Red

    # -------------------------------------------------------------------------
    # Execution Loop
    # -------------------------------------------------------------------------
    for getter_name, label, method_name, setter_bool in FAULT_TESTS:
        print(f"\n--- Testing Fault {label} ---")

        # Dynamic setter method retrieval
        setter = getattr(ate, method_name)

        result, color = _run_single_fault_test(
            getter_name, label, setter, setter_bool, dut, chan
        )

        tdata.append([f"Fault {label} Generated and Cleared", result])
        tcolor.append(color)

    # -------------------------------------------------------------------------
    # Build Report
    # -------------------------------------------------------------------------
    row_h = [0.35 * inch] + [0.27 * inch] * (len(tdata) - 1)
    col_w = [4 * inch, 2 * inch]

    style = [
        ("SPAN", (0, 0), (1, 0)),
        ("ALIGN", (0, 0), (1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (1, 0), 16),
        ("VALIGN", (0, 0), (1, len(tdata) - 1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BOX", (0, 0), (-1, -1), 2, colors.black),
        ("BACKGROUND", (0, 0), (1, 0), colors.lemonchiffon),
    ]

    for i in range(1, len(tdata)):
        bg = colors.lightgreen if tcolor[i - 1] == 0 else colors.pink
        style.append(("BACKGROUND", (1, i), (1, i), bg))

    section.append(Spacer(1, 0.2 * inch))
    section.append(Table(tdata, col_w, row_h, style=style))

if __name__ == "__main__":
    _dut = DUT()
    _dut.prompt_inputs()

    # Initialize hardware connection
    _dut.init()
    _ate = ATE()
    #  chan=1
    _ctx, _pdf_path = start_report(_dut)
    for _chan in _dut.model.channels:
        with channel_section(_ctx, _chan) as _sec:
            ate_fault_tests(_dut, _ate, _sec, _chan)
    finalize_report(_ctx)

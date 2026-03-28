"""
ATE Fault Test Submodule

This module executes automated fault testing for Power Supply
Controllers (PSC). It interfaces with the Automated Test Equipment
(ATE) to inject specific hardware faults (e.g., Interlocks,
DCCT faults) and verifies that the PSC correctly detects and latches
these faults via EPICS PV monitoring.

Key Features:
    - **EpicsMonitor**: A context manager that wraps `camonitor` in a
      background thread to capture transient fault events without blocking
      the test execution.
    - **Retry Logic**: Both fault detection and clearing sequences include
      automatic retries to handle timing jitter or hardware race conditions.
    - **Report Generation**: Automatically builds a color-coded status table
      for the PDF test report.

Modified: M. Capotosto 1-1-2026
"""

from __future__ import annotations
import subprocess
import threading
import time  # Fix: Import the module, not specific functions, to \
#            # avoid conflicts
from queue import Queue, Empty
from typing import Any

from reportlab.lib.units import inch
from reportlab.platypus import Table, Spacer
from reportlab.lib import colors

from Common.initialize_dut import DUT
from Common.EPICS_Adapters.ate_epics import ATE

# =============================================================================
# camonitor helpers
# =============================================================================


class EpicsMonitor:
    """
    Context manager that spawns a 'camonitor' subprocess to watch a PV.
    Ensures the background process is killed strictly upon exit to prevent
    zombie processes.

    Attributes:
        pvname (str): The EPICS process variable to monitor.
        last_known_value (int): The most recent integer value parsed
                                from stdout.
    """
    def __init__(self, pvname: str):
        self.pvname = pvname
        self.process: subprocess.Popen | None = None
        self.queue: Queue = Queue()
        self.thread: threading.Thread | None = None
        self.last_known_value: int = 0
        self.running = False

    def _enqueue_output(self, pipe):
        """
        Background thread entry point.
        Reads lines from the subprocess stdout and pushes them to the queue.
        """
        try:
            for line in iter(pipe.readline, ""):
                self.queue.put(line)
        except (ValueError, OSError):
            pass  # Process likely killed
        finally:
            pipe.close()

    def __enter__(self):
        """Start the camonitor process and reader thread."""
        self.process = subprocess.Popen(
            ["camonitor", self.pvname],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,  # Line buffered
            text=True,
            close_fds=True  # Ensure file descriptors aren't leaked
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
        """Kill the process immediately when leaving the 'with' block."""
        self.running = False
        if self.process:
            try:
                self.process.terminate()  # Try nice termination first
                # give it a moment or just kill if timing is critical
                # For tests, kill is usually fine and faster
                self.process.kill()
                self.process.wait(timeout=1)
            except (subprocess.TimeoutExpired, OSError):
                pass

            # Ensure pipes are closed to prevent FD leaks
            if self.process.stdout:
                self.process.stdout.close()
            if self.process.stderr:
                self.process.stderr.close()

    def get_latest(self) -> int:
        """
        Drains the queue to get the most recent value.
        Returns the last seen value (or 0 if nothing seen yet).
        """
        # Drain the queue to get the freshest update
        latest_line = None
        while not self.queue.empty():
            try:
                latest_line = self.queue.get_nowait()
            except Empty:
                break

        if latest_line:
            try:
                # Format: "PVNAME   <date> <time>   VALUE"
                # We want the last token.
                val_str = latest_line.strip().split()[-1]
                self.last_known_value = int(val_str)
            except (ValueError, IndexError):
                # Ignore parsing errors (e.g., disconnection messages)
                pass

        return self.last_known_value


# =============================================================================
# Fault Configuration Table
# =============================================================================

FAULT_TESTS = [
    (0x80,  "#1",    "set_flt1", True),
    (0x100, "#2",    "set_flt2", True),
    (0x200, "SPARE", "set_fltspare", True),
    (0x40,  "DCCT",  "set_dcct_fault_channel", False),
]


def _run_single_fault_test(mask: int, label: str, setter: Any,
                           setter_bool: bool, dut: DUT, chan: int) -> \
                           tuple[str, int]:
    """
    Run ONE fault test sequence (Trigger -> Detect -> Clear) with retries.

    Args:
        mask (int): The bitmask to check in the Fault Status word.
        label (str): Human-readable name of the fault (e.g., "#1", "DCCT").
        setter (func): The ATE method used to inject the fault.
        setter_bool (bool): True if the setter takes (chan, bool), False if
                            it takes (chan) or (0).
        dut (DUT): Device Under Test interface.
        chan (int): The channel to test.

    Returns:
        tuple[str, int]: ("PASS"/"FAIL", ColorFlag). ColorFlag 0=Green, 1=Red.
    """

    # -------------------------------------------------------------
    # Helper: run the "fault trigger + detection" portion once
    # -------------------------------------------------------------
    def run_detection_pass() -> bool:
        """
        Injects the fault via ATE and monitors EPICS for the
        corresponding bit.

        Returns True if the fault is detected in either Live or
        Latched records.
        """
        live_pv = dut.psc.pv("FaultsLive-I", ch=chan)
        lat_pv = dut.psc.pv("FaultsLat-I", ch=chan)

        # Context manager handles cleanup automatically
        with EpicsMonitor(live_pv) as live_mon, EpicsMonitor(lat_pv) \
                as lat_mon:

            # Prime the monitors (drain initial values)
            time.sleep(0.5)  # Increased slightly to ensure camonitor starts
            live_mon.get_latest()
            lat_mon.get_latest()

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
                live_val = live_mon.get_latest()
                lat_val = lat_mon.get_latest()

                if (live_val & mask) or (lat_val & mask):
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
        that all fault bits have cleared.
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

        # 3. Verify PVs show clear
        # Poll for up to 20 seconds (200 * 0.05s)
        for _ in range(200):
            live_raw = int(dut.psc.get_live_faults(chan))
            lat_raw = int(dut.psc.get_latched_faults(chan))

            bit_cleared_live = (live_raw & mask) == 0
            bit_cleared_lat = (lat_raw & mask) == 0
            if bit_cleared_live == 1 and bit_cleared_lat == 1:
                clear_pass = True
                return clear_pass
            else:
                time.sleep(0.1)
                clear_pass = False

        if clear_pass is True:
            return True

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
    Main driver for automated ATE Fault Testing using event-driven EPICS.

    Orchestrates the testing of multiple hardware fault conditions (defined in
    FAULT_TESTS) by sequentially injecting, detecting, and clearing them.
    Generates a ReportLab Table with color-coded results.

    Args:
        dut (DUT): Device Under Test abstraction.
        ate (ATE): Automated Test Equipment control abstraction.
        section (list): ReportLab flowables list to append the results
                        table to.
        chan (int): The channel number under test.
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
    for mask, label, method_name, setter_bool in FAULT_TESTS:
        print(f"\n--- Testing Fault {label} ---")

        # Dynamic method retrieval
        setter = getattr(ate, method_name)

        result, color = _run_single_fault_test(
            mask, label, setter, setter_bool, dut, chan
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

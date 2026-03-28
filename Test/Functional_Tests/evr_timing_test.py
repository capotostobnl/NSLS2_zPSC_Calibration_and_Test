"""EVR Timing Test Submodule
Modified M. Capotosto 1/1/2026
Original: Tony Caracappa
"""

import os
from time import sleep
from epics import caget, caput
from matplotlib import pyplot as plt
from reportlab.platypus import Image
from reportlab.lib.units import inch

from Common.initialize_dut import DUT
from Test.test_report_generator import ReportContext

#######################################################################
# ******Disable Scientific Notation Conversions on X/Y Axis Plots******
plt.rcParams['axes.formatter.useoffset'] = False
plt.rcParams['axes.formatter.limits'] = [-7, 7]
########################################################################


def evr_timing_test(dut: DUT, ctx: ReportContext) -> None:
    """
    Verifies the EVR (Event Receiver) timestamp functionality over a
    30-second interval.

    This test performs the following steps:
      1. Resets the EVR logic via EPICS.
      2. Waits for the timestamp to start incrementing (initial tick).
      3. Records timestamps for 30 seconds.
      4. Verifies that every time increment is exactly 1 second.
      5. Generates a validation plot and appends it to the PDF report.

    Args:
        dut: The Device Under Test instance containing PV prefixes and
             configuration.
        ctx: The ReportContext for storing test results and generating the PDF.

    Raises:
        RuntimeError: If critical PVs are unreachable, or if the EVR timestamp
                      fails to increment (stalls) for more than 5 seconds.
    """
    evr_ts_pv = dut.pv_prefix + "TS-S-I"
    evr_date_pv = dut.pv_prefix + "Timestamp-I.VALA"

    # --- Program EVR and reset, but wait for the puts to complete ---
    caput(f"{dut.pv_prefix}EVR:1Hz-EventNo-SP", 32, wait=True, timeout=2.0)
    caput(f"{dut.pv_prefix}EVR:Reset-SP", 1, wait=True, timeout=2.0)
    sleep(0.1)
    caput(f"{dut.pv_prefix}EVR:Reset-SP", 0, wait=True, timeout=2.0)

    # OPTIONAL: short settle time
    sleep(0.5)

    timestamp: list[float] = []
    elapsed_time: list[float] = []

    # --- Get date string (same as before) ---
    date_array = caget(evr_date_pv)
    if date_array is None:
        date_text = ""
    else:
        date_text = "".join(chr(i) for i in date_array if i != 0)

    # --- Wait for the first EVR tick after reset ---
    initial_ts = caget(evr_ts_pv)
    if initial_ts is None:
        raise RuntimeError(f"PV {evr_ts_pv} returned None after EVR reset")

    print("Waiting for first EVR timestamp tick...")
    t0 = None
    t_last = None
    for _ in range(20):  # ~10 seconds max (with 0.5 s sleeps)
        current_ts = caget(evr_ts_pv)
        if current_ts is None:
            sleep(0.5)
            continue
        if current_ts != initial_ts:
            t0 = current_ts
            t_last = current_ts
            break
        sleep(0.5)

    if t0 is None or t_last is None:
        raise RuntimeError("EVR timestamp never started after reset.")

    print(f"First tick detected: T0 = {t0}")

    i = 0
    ts_error = 0
    zero_count = 0

    print("Collecting 30 seconds of EVR Timestamps:")
    f, ax = plt.subplots(1, 1, figsize=(7, 5))

    started = False

    # --- Main acquisition loop (mostly unchanged) ---
    while i < 31:
        current_ts = caget(evr_ts_pv)
        if current_ts is None:
            raise RuntimeError(f"PV {evr_ts_pv} returned None")

        time_diff = current_ts - t_last

        if time_diff > 0:
            if not started:
                # First usable tick: initialize T0/t_last and don't check
                # time_diff yet
                t0 = current_ts
                t_last = current_ts
                started = True
                elapsed_time.append(0.0)
                timestamp.append(0.0)
                print(f"First stable tick: T0 = {t0}")
            else:
                rel = current_ts - t0
                elapsed_time.append(rel)
                if time_diff != 1:
                    ts_error = 1
                timestamp.append(rel)
                print(f"TD={time_diff} EvrTS[{i}] = {current_ts}  : "
                      f"Error = {ts_error}")
                t_last = current_ts
                i += 1
            zero_count = 0
        else:
            zero_count += 1
            if zero_count > 5:
                raise RuntimeError("Timestamp Not Changed for 5 seconds..."
                                   "Stopping Program.")

        sleep(0.7)

        # --- Plot update ---
        ax.clear()
        ax.plot(elapsed_time, timestamp, "-o")
        ax.grid(True)
        ax.set_xlabel("Elapsed Time (Seconds)")
        ax.set_ylabel("TmStamp - T0")
        ax.set_title("EVR Timestamp Test")

        mstr = f"T0: {t0} = {date_text}"
        ax.text(
            0.05,
            0.95,
            mstr,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=ctx.theme.props,
        )
        plt.pause(0.01)

    # PASS/FAIL annotation (unchanged)
    if ts_error == 0:
        mstr = "Test: All time increments equal 1 second? : PASS"
        ax.text(
            0.2,
            0.1,
            mstr,
            transform=ax.transAxes,
            fontsize=12,
            verticalalignment="top",
            bbox=ctx.theme.good,
        )
        print("EVR Timestamp Test PASSED.")
    else:
        mstr = "Test: All time increments equal 1 second? : FAIL"
        ax.text(
            0.2,
            0.1,
            mstr,
            transform=ax.transAxes,
            fontsize=12,
            verticalalignment="top",
            bbox=ctx.theme.bad,
        )
        print("EVR Timestamp Test FAILED.")

    plt.pause(0.01)

    img_path = os.path.join(dut.raw_data_dir, "EVR_Timestamp.png")
    f.savefig(img_path)

    # Cleanup / add to report
    sleep(1)
    plt.ioff()
    plt.close(f)
    plt.pause(0.1)

    ctx.elements.append(Image(img_path, 6 * inch, 4 * inch))

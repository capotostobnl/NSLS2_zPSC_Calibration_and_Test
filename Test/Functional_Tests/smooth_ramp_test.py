"""Smooth Ramp Test Submodule

Modified M. Capotosto 11-9-2025
"""

import os
from time import sleep
import numpy as np
from matplotlib import pyplot as plt
from reportlab.platypus import Image, PageBreak
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from Test.test_report_generator import ReportContext
from Common.initialize_dut import DUT
from Common.EPICS_Adapters.ate_epics import ATE

#######################################################################
# ******Disable Scientific Notation Conversions on X/Y Axis Plots******
plt.rcParams['axes.formatter.useoffset'] = False
plt.rcParams['axes.formatter.limits'] = [-7, 7]
########################################################################


def smooth_ramp_test(dut: DUT,
                     ate: ATE,
                     section: list,
                     chan: int,
                     ctx: ReportContext,
                     drive_chan: tuple,
                     readback_chan: tuple
                     ):
    """
    Executes a high-speed waveform capture and analysis during a smooth
    current ramp.

    The function performs the following sequence:
    1.  **Hardware Prep**: Configures the grounding relay (IGND) via the ATE,
        clears active faults, and sets the PSC to 'Smooth' operation mode.
    2.  **Initial Move**: Ramps the channel to the 'start_setpoint' and waits
        for the model-defined settling time to ensure a stable baseline.
    3.  **Dynamic Ramp**: Executes a ramp to the 'end_setpoint' at the
        per-channel slew rate specified in the model configuration.
    4.  **Snapshot Capture**: Triggers a 10kHz hardware snapshot (User Shot)
        during the ramp and polls the trigger status until the data transfer
        is complete.
    5.  **Waveform Analysis**: Retrieves 8 distinct signal waveforms (DAC,
        DCCTs, Error, Voltage, etc.) and performs a statistical Pass/Fail
        analysis on the Ground Current (IGND) stability.
    6.  **Reporting**: Generates multi-page PDF output by looping through
        captured waveforms, organizing them into a professional layout
        (3 plots per page).

    Args:
        dut (DUT): The Device Under Test object containing the PSC adapter
            and the model-specific ramp parameters (SmoothRampTestParams).
        ate (ATE): The Automated Test Equipment adapter for controlling
            external grounding hardware.
        section (list): A list of ReportLab Flowables to which the title,
            plots, and spacers will be appended.
        chan (int): The 1-indexed channel number (1-4) to be tested.
        ctx (ReportContext): The reporting utility used for consistent
            styling, color themes, and directory path management.

    Returns:
        None: All data is saved to disk as PNG files and appended
            directly to the 'section' report list.

    Raises:
        AssertionError: If the PSC adapter is not properly initialized.
        AttributeError: If the requested channel is missing from the
            model's start, end, or rate configurations.
    """
    assert dut.psc is not None

    ignd_sp = 0.1
    ate.set_ignd_channel(chan)
    sleep(0.5)
    ate.set_ignd_value(ignd_sp, chan, dut)
    sleep(3)

    wfm_pvs = dut.psc.WfmPV
    dut.psc.set_op_mode(drive_chan, 0)  # Set PS Mode to SMOOTH
    sleep(1)

    ramp_params = dut.model.smooth
    start_sp = getattr(ramp_params.start_setpoints, f"ch{drive_chan}")
    end_sp = getattr(ramp_params.end_setpoints, f"ch{drive_chan}")
    ramp_rate = getattr(ramp_params.ramp_rate, f"ch{drive_chan}")
    tolerance = ramp_params.tolerance
    settling_time = ramp_params.settling_time

    dut.psc.set_rate(drive_chan, ramp_rate)
    print(f"Moving to Start: {start_sp}A")
    dut.psc.set_dac_setpt(drive_chan, start_sp)

    timeout = 30
    elapsed = 0

    # Move DAC Setpt to some non-zero value to prevent hanging on bug...
    dut.psc.set_dac_setpt(drive_chan, 1)
    sleep(0.5)

    while abs(dut.psc.get_dac(drive_chan) - start_sp) > 0.5:  # 0.5A tolerance
        if elapsed >= timeout:
            print("Timeout reached! PS failed to reach start setpoint.Exiting")
            exit()

        print("Waiting for stable baseline... Current: "
              f"{dut.psc.get_dac(drive_chan)}A")
        dut.psc.set_dac_setpt(drive_chan, start_sp)
        print(f"Setpoint set to: Channel: {chan}, SP: {start_sp}")
        sleep(1)
        elapsed += 1

    print(f"Baseline reached. Settling for {settling_time}s...")
    sleep(settling_time)

    print(f"Ramping: {start_sp}A -> {end_sp}A @ {ramp_rate}A/s")
    dut.psc.set_dac_setpt(drive_chan, end_sp)

    sleep(2)  # Wait 2 Seconds before taking Snapshot
    print(f"DAC SP: {end_sp}\nDAC RB: {dut.psc.get_dac(drive_chan)}(Ramping!)")
    dut.psc.user_shot(readback_chan)  # Take the Snapshot.
    sleep(2)
    while dut.psc.is_user_trig_active(readback_chan) > 0:
        sleep(1)
        print("Wating for Smooth Snapshot data.....")
    sleep(6)
    print(f"DAC SP: {end_sp} \nDAC RB: {dut.psc.get_dac(drive_chan)}")

    # Waveform configuration list
    waveform_metadata = [
        # pylint: disable=line-too-long
        # DATA           Y_LABEL       TITLE            LABEL     # noqa: E501
        (wfm_pvs.DAC,   "Current (A)", "DAC Loopback", "DAC"),    # noqa: E501
        (wfm_pvs.DCCT1, "Current (A)", "DCCT 1",       "DCCT1"),  # noqa: E501
        (wfm_pvs.DCCT2, "Current (A)", "DCCT 2",       "DCCT2"),  # noqa: E501
        (wfm_pvs.ERR,   "Current (A)", "ERROR",        "ERROR"),  # noqa: E501
        (wfm_pvs.REG,   "Current (A)", "REG",          "REG"),    # noqa: E501
        (wfm_pvs.VOLT,  "Voltage (V)", "PS Voltage",   "VOLT"),   # noqa: E501
        (wfm_pvs.GND,   "Current (A)", "Ground",       "IGND"),   # noqa: E501
        (wfm_pvs.SPARE, "Current (A)", "SPARE",        "SPARE")   # noqa: E501
        # pylint: enable=line-too-long
    ]

    channel_flags = getattr(dut.model.smooth.waveforms, f"ch{chan}")

    waveform_configs = []
    for pv, y_label, title, label in waveform_metadata:
        # 2. Check the flag on the specific channel object, not the container
        # If channel_flags is None (undefined in model), default to True (plot everything)
        if channel_flags is None or getattr(channel_flags, label, True):
            data = dut.psc.get_wfm(chan, pv)
            waveform_configs.append((data, y_label, title, label))
    plt.ion()

    for data, y_label, title, label in waveform_configs:
        fig, axis = plt.subplots(figsize=(8, 4))
        axis.plot(data)
        axis.grid(True)
        axis.set_xlabel("10KHz Samples")
        axis.set_ylabel(y_label)
        axis.set_title(f"Ch{chan} {title} Smooth Test")
        plt.pause(0.1)

        if label == "IGND":  # Add pass/fail test
            ignd_avg = float(np.mean(data))
            diff = abs(ignd_sp - ignd_avg)

            is_pass = diff < tolerance
            status = "PASS" if is_pass else "FAIL"
            theme = ctx.theme.good if is_pass else ctx.theme.bad

            # Format the box text using model-specific tolerance
            test_str = f"Test: |Avg-0.1| < {tolerance*1000:.0f}mA? : {status}"
            axis.text(0.5, 0.07, test_str, transform=axis.transAxes,
                      ha="center", bbox=theme)

        save_path = os.path.join(dut.raw_data_dir,
                                 f"Chan{chan}_{label}_Smooth.png")
        fig.savefig(save_path)
        plt.close(fig)
        plt.pause(0.1)

    base_style = ctx.styles["Normal"]
    mstr = f"Smooth Test Results: CH{chan}"
    paragraph_style = ParagraphStyle(
        "Custom",
        parent=base_style,
        fontName="Helvetica",
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
    )

    title = Paragraph(mstr, paragraph_style)
    section.append(PageBreak())
    section.append(title)
    section.append(Spacer(1, 0.2 * inch))

    # Loop through the labels defined in waveform_configs to add images
    for i, (_, _, _, label) in enumerate(waveform_configs):
        img_path = os.path.join(dut.raw_data_dir, f"Chan{chan}_{label}"
                                "_Smooth.png")

        # Add the image and a small spacer
        section.append(Image(img_path, 7 * inch, 3 * inch))
        section.append(Spacer(1, 0.1 * inch))

        # Tidy up the layout: Add a page break and repeat the title after
        # every 3 images
        if (i + 1) % 3 == 0 and (i + 1) < len(waveform_configs):
            section.append(PageBreak())
            section.append(title)
            section.append(Spacer(1, 0.2 * inch))

    dut.psc.set_dac_setpt(chan, 0)
    return

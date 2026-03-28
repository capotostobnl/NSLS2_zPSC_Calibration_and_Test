"""
Jump Test Submodule

This module implements the Step Response test for Power Supply Controllers.
It relies on the `PSCModel` registry for unit-specific setpoints and
tolerances, ensuring a generic execution flow for various magnet types.
"""
import os
from time import sleep
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec
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


def jump_test(dut: DUT,
              ate: ATE,
              section: list,
              chan: int,
              ctx: ReportContext,
              drive_chan: tuple,
              readback_chan: tuple):
    """
    Executes a Step Response (Jump) test and generates diagnostic plots.

    The test stabilizes the PSC at a baseline current, performs a sudden
    current step (jump), and captures high-speed waveform data to analyze
    control loop stability, overshoot, and ground current (IGND) behavior.

    Args:
        dut: The Device Under Test object containing model specs and
        PSC interface.
        ate: The Automated Test Equipment interface for external
        hardware control.
        section: The list of ReportLab elements to append results to.
        chan: The specific PSC channel number being tested.
        ctx: The reporting context containing styles and theme settings.

    Raises:
        SystemExit: If the hardware fails to stabilize at the baseline
        setpoint.
    """

    assert dut.psc is not None

    # --- HARDWARE INITIALIZATION ---
    # Configure ground current monitoring and snapshot window
    jump_params = dut.model.jump
    start_sp = getattr(jump_params.start_setpoints, f"ch{drive_chan}")
    step_size = getattr(jump_params.step_size, f"ch{drive_chan}")
    target_sp = start_sp + step_size
    window = jump_params.sample_window
    tolerance = jump_params.tolerance

    ignd_setpoint = 0.1
    ate.set_ignd_channel(drive_chan)
    sleep(0.5)
    ate.set_ignd_value(ignd_setpoint, drive_chan, dut)
    print(f"Set CH{drive_chan} ignd to {ignd_setpoint}, waiting 5 seconds settling"
          " time...")
    sleep(5)

    wfm_pvs = dut.psc.WfmPV
    dut.psc.set_wfm_xmin(readback_chan, 0)
    dut.psc.set_wfm_xmax(readback_chan, 100000)
    dut.psc.set_op_mode(drive_chan, 3)  # Set Mode to Jump
    dut.psc.flush_io()

    # --- BASELINE STABILIZATION ---
    # Ensure the PSC is at the starting current before the jump
    dut.psc.set_dac_setpt(drive_chan, start_sp)
    print(f"DAC SP: {start_sp} \nDAC RB: {dut.psc.get_dac(drive_chan)}(ramping)")
    dut.psc.flush_io()
    sleep(10)

    timeout = 0
    while int(dut.psc.get_dac(drive_chan)) not in \
            range(int(start_sp)-1, int(start_sp)+1):
        print("Waiting for DAC SP to stabilize")
        dut.psc.set_dac_setpt(drive_chan, start_sp)
        timeout = timeout + 1
        sleep(1)
        if timeout == 30:
            print("Unable to reach Start SP in 30 seconds..."
                  f"DAC SP: {start_sp}A, DAC RB: {dut.psc.get_dac(drive_chan)}")
            raise SystemExit

    # --- TRANSIENT CAPTURE ---
    # Perform the jump and trigger high-speed snapshot
    print(f"Jumping to: {target_sp}A (Step: {step_size}A)")
    dut.psc.set_dac_setpt(drive_chan, target_sp)
    dut.psc.flush_io()
    sleep(0.1)
    print(f"DAC SP: {start_sp} \nDAC RB: {dut.psc.get_dac(chan)}(ramping)")

    dut.psc.user_shot(readback_chan)
    sleep(2)
    while dut.psc.is_user_trig_active(readback_chan) > 0:
        sleep(1)
        print("Waiting for Jump Snapshot data.....")
    sleep(4)

    # --- PLOTTING & REPORTING ---
    # Generate split-view plots and append to PDF

    # --- DATA ANALYSIS & INDEXING ---
    # Detect jump location and define crop windows
    trigger_pv = wfm_pvs.DAC # Default
    try:
        flags = getattr(dut.model.jump.waveforms, f"ch{readback_chan}")
        if flags and not getattr(flags, "DAC", True):
            if getattr(flags, "REG", False): 
                trigger_pv = wfm_pvs.REG
            elif getattr(flags, "VOLT", False): 
                trigger_pv = wfm_pvs.VOLT
    except AttributeError:
        pass # Keep default

    print(f"Calculating Jump Index using Trigger PV: {trigger_pv}")

    # 2. Fetch Trigger Data and Calculate Window
    trigger_data = np.asarray(dut.psc.get_wfm(readback_chan, trigger_pv))
    
    try:
        # Find the index of maximum change (the jump)
        jump_idx = int(np.argmax(np.abs(np.diff(trigger_data))))
    except ValueError:
        jump_idx = 0
    
    print(f"Detected Jump at Sample Index: {jump_idx}")

    # Define the shared window for ALL plots
    t_start = max(0, jump_idx - window)
    t_end = min(len(trigger_data), jump_idx + window)

    waveform_metadata = [
        # pylint: disable=line-too-long
        # DATA           Y_LABEL       F_TITLE          Z_TITLE,            LABEL     # noqa: E501
        (wfm_pvs.DAC,   "Current (A)", "DAC Loopback", "DAC Transition",   "DAC"),    # noqa: E501
        (wfm_pvs.DCCT1, "Current (A)", "DCCT 1",       "DCCT1 Transition", "DCCT1"),  # noqa: E501
        (wfm_pvs.DCCT2, "Current (A)", "DCCT 2",       "DCCT2 Transition", "DCCT2"),  # noqa: E501
        (wfm_pvs.ERR,   "Current (A)", "ERROR",        "Error Transition", "ERROR"),  # noqa: E501
        (wfm_pvs.REG,   "Current (A)", "REG",          "REG Transition",   "REG"),    # noqa: E501
        (wfm_pvs.VOLT,  "Voltage (V)", "PS Voltage",   "VOLT Transition",  "VOLT"),   # noqa: E501
        (wfm_pvs.GND,   "Current (A)", "Ground",       "IGND Transition",  "IGND"),   # noqa: E501
        (wfm_pvs.SPARE, "Current (A)", "SPARE",        "SPARE Transition", "SPARE")   # noqa: E501
        # pylint: enable=line-too-long
    ]


    channel_flags = getattr(dut.model.jump.waveforms, f"ch{readback_chan}")

    waveform_configs = []

    for pv, y_label, f_title, z_title, label in waveform_metadata:
        # 2. Check the flag on the specific channel object, not the container
        # If channel_flags is None (undefined in model), default to True (plot everything)
        if channel_flags is None or getattr(channel_flags, label, True):
            data = dut.psc.get_wfm(readback_chan, pv)
            waveform_configs.append((data, y_label, f_title, z_title, label))

    plt.ion()

    for data, y_lab, f_title, z_title, label in waveform_configs:

        # Calculate start/end based on THIS signal's jump location
        t_start = max(0, jump_idx - window)
        t_end = min(len(data), jump_idx + window)

        fig = plt.figure(figsize=(8, 4))
        gs = GridSpec(1, 3, figure=fig)

        # Left side: Full waveform overview (2/3 of the width)
        ax_full = fig.add_subplot(gs[0, 0:2])
        ax_full.plot(data)
        ax_full.set_title(f"Ch{readback_chan} {f_title} Jump Test")
        ax_full.set_ylabel(y_lab)
        ax_full.set_xlabel("10KHz Samples")
        ax_full.grid(True)

        # Right side: Zoomed transition (1/3 of the width)
        ax_zoom = fig.add_subplot(gs[0, 2])
        ax_zoom.plot(data[t_start:t_end])
        ax_zoom.set_title(z_title)
        ax_zoom.set_xlabel("Samples")
        ax_zoom.grid(True)

        # Integrated IGND Pass/Fail Logic (Only for the IGND plot)
        if label == "IGND":
            avg = float(np.mean(data))
            diff = abs(ignd_setpoint - avg)
            is_pass = diff < tolerance
            theme = ctx.theme.good if is_pass else ctx.theme.bad
            res = "PASS" if is_pass else "FAIL"

            box_text = f"Test: |Avg-0.1|<{tolerance*1000:.0f}mA? : {res}"
            ax_full.text(0.5, 0.07, box_text, transform=ax_full.transAxes,
                         ha="center", bbox=theme)

        plt.tight_layout()
        save_path = os.path.join(dut.raw_data_dir, f"Chan{readback_chan}_"
                                 f"{label}_Jump.png")
        fig.savefig(save_path)
        plt.close(fig)
        plt.pause(0.1)

    base_style = ctx.styles["Normal"]
    mstr = f"Jump Test Results: Ch{readback_chan}"
    paragraph_style = ParagraphStyle(
        "Custom",
        parent=base_style,
        fontName="Helvetica",
        fontSize=16,
        leading=20,  # Optional: line spacing
        alignment=TA_CENTER,
    )

    mstr = f"Jump Test Results: CH{readback_chan}"
    title_para = Paragraph(mstr, paragraph_style)

    # Start the reporting
    section.append(PageBreak())
    section.append(title_para)
    section.append(Spacer(1, 0.2 * inch))

    # REPLACE all manual Image/Spacer lines with this loop:
    for i, (_, _, _, _, label) in enumerate(waveform_configs):
        img_path = os.path.join(dut.raw_data_dir, f"Chan{readback_chan}_"
                                f"{label}_Jump.png")

        if os.path.exists(img_path):
            section.append(Image(img_path, 7 * inch, 3 * inch))
            section.append(Spacer(1, 0.1 * inch))

            # Logic to keep the report tidy (3 plots per page)
            if (i + 1) % 3 == 0 and (i + 1) < len(waveform_configs):
                section.append(PageBreak())
                section.append(title_para)
                section.append(Spacer(1, 0.2 * inch))

    print(f"Jump Test for CH{readback_chan} complete. Returning to 0A.")
    dut.psc.set_dac_setpt(drive_chan, 0)
    dut.psc.flush_io()

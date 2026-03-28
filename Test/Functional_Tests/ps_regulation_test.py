"""Power Supply Regulation Test

Modified M. Capotosto 12/31/2025
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


def ps_regulation_test(dut: DUT,
                       ate: ATE,
                       section: list,
                       chan: int,
                       ctx: ReportContext,
                       drive_chan: tuple,
                       readback_chan: tuple):
    """
    Executes a high-precision stability and regulation test on a single
    PSC channel.

    The function performs the following sequence:
    1.  **Hardware Prep**: Configures grounding, clears latched faults, and
        sets the model-specific ramp rate.
    2.  **Stabilization**: Ramps the current to the target setpoint (defined
        in dut.model) and waits for the specified settling time.
    3.  **Data Collection**: Captures high-speed loopback and DCCT register
        readings for the duration specified by num_samples and sample_interval.
    4.  **Analysis**: Calculates the mean deviation and compares it against
        the model's tolerance threshold (Amps).
    5.  **Visualization**: Generates stability and histogram plots for
        Loopback, DCCT1, and DCCT2, saving them as PNGs.
    6.  **Reporting**: Appends the analysis results and generated plots to
        the ReportContext for PDF generation.

    Args:
        dut (DUT): The Device Under Test object containing the psc adapter
            and the model specification (PSCModel).
        ate (ATE): The Automated Test Equipment adapter for controlling
            external instrumentation (e.g., grounding relays).
        section (list): A list of ReportLab Flowables to which this test's
            results and images will be appended.
        chan (int): The 1-indexed channel number (1-4) to be tested.
        ctx (ReportContext): The reporting utility used for consistent
            styling, themes, and path management.

    Returns:
        None: Results are appended directly to the 'section' list and
        saved to the 'dut.raw_data_dir'.

    Raises:
        AssertionError: If the PSC adapter is not initialized.
        AttributeError: If the selected channel is not defined in the
            dut.model specification.
    """
    assert dut.psc is not None

    print(f"Preparing PSC Channel {chan} for Regulation test...")
    dut.psc.set_fault_mask_all(drive_chan, 0)
    ate.set_ignd_channel(drive_chan)
    ate.set_ignd_value(0, drive_chan, dut)
    print("ATE ignd Set...")
    dut.psc.set_dac_setpt(drive_chan, 0)

    dut.psc.set_rate(drive_chan, dut.model.reg.ramp_rate)

    dut.psc.set_dac_setpt(drive_chan, 0)

    for i in dut.model.channels:
        dut.psc.set_fault_mask_all(chan, 0)
        dut.psc.set_power_on1(i, 1)
        dut.psc.set_enable_on2(i, 1)
        dut.psc.set_op_mode(i, 0)
        dut.psc.set_park(i, 0)
        dut.psc.set_dac_setpt(i, 0)

    sleep(0.2)

    # Look up the current setpoint in the class by channel
    setpoint = getattr(dut.model.reg.setpoints, f"ch{drive_chan}")
    print(f"Model: {dut.model.display_name} | Chan: {readback_chan} | "
          f"setpoint: {setpoint}A")

    dut.psc.set_dac_setpt(drive_chan, setpoint)
    print(f"Chan: {drive_chan}, setpoint: {setpoint}")
    print("PSC rate, DAC setpoint, Enable, Park, and Power bits set...")

    settling_time = getattr(dut.model.reg, 'settling_time')
    print(f"Sleeping {settling_time} seconds for currents to stabilize...")
    sleep(settling_time)

    samples = dut.model.reg.num_samples
    interval = dut.model.reg.sample_interval
    tolerance = dut.model.reg.tolerance

    run = 0
    
    sp_sat = False

    while run < 6:

        if not sp_sat:
            dac_rb = dut.psc.get_dac(drive_chan)
            print(f"DAC RB Not satisfied to SP yet...sleeping 5s...Attempt "
                  f"{run+1}")
            print(f"DAC RB Val: {dac_rb}")
            run += 1
            dut.psc.set_dac_setpt(drive_chan, setpoint)
            sleep(5)

            dac_rb = dut.psc.get_dac(drive_chan)
            sp_sat = (setpoint - 0.05) < dac_rb < (setpoint + 0.05)
            sleep(2)

        elif sp_sat:
            print("SP Satisfied...continuing...")
            break
    
    if not sp_sat: 
        raise RuntimeError("DAC RB Unable to be satisfied after 6 attempts! Exiting!")
    run = 0
    
    # Collect 1 minute of data:
    collection_time = samples * interval
    print(f"Preparing to collect {collection_time} seconds of data "
          f"for Channel {readback_chan}")
    loopback_rb = []
    dcct1_rb = []
    dcct2_rb = []
    f, ax = plt.subplots(3, 1, figsize=(6, 9.5))
    plt.ion()
    print("*******************************************\n")
    print(f"Channel {readback_chan}: ")
    for i in range(0, samples):
        print(f"Collecting Regulation Data for Channel {readback_chan} "
              f"datapoint {i+1} of {samples}...")
        v_dac = dut.psc.get_dac(readback_chan)
        v_dcct1 = dut.psc.get_dcct1(readback_chan)
        v_dcct2 = dut.psc.get_dcct2(readback_chan)
        loopback_rb.append(v_dac)
        dcct1_rb.append(v_dcct1)
        dcct2_rb.append(v_dcct2)
        ax[0].clear()
        ax[1].clear()
        ax[2].clear()
        ax[0].plot(loopback_rb)
        ax[1].plot(dcct1_rb)
        ax[2].plot(dcct2_rb)
        plt.pause(0.1)
        sleep(interval)

    plt.ioff()
    plt.close(f)
    plt.pause(0.1)

    loopback_rb_avg = np.mean(loopback_rb)
    loopback_rb = (loopback_rb - loopback_rb_avg) * 1000
    loopback_rb_err = abs(loopback_rb_avg - setpoint)
    dcct1_rb_avg = np.mean(dcct1_rb)
    dcct1_rb = (dcct1_rb - dcct1_rb_avg) * 1000
    dcct1_rb_err = abs(dcct1_rb_avg + setpoint)
    dcct2_rb_avg = np.mean(dcct2_rb)
    dcct2_rb = (dcct2_rb - dcct2_rb_avg) * 1000
    dcct2_rb_err = abs(dcct2_rb_avg + setpoint)
    print(loopback_rb_err, dcct1_rb_err, dcct2_rb_err)

    # Define the configurations for the three plots
    # Format: (data, average, title_string, label_string)
    plot_configs = [
        (loopback_rb,  loopback_rb_avg,  "Loopback", "Loopback"),
        (dcct1_rb, dcct1_rb_avg, "DCCT 1",   "DCCT1"),
        (dcct2_rb, dcct2_rb_avg, "DCCT 2",   "DCCT2")
    ]

    # Generate and save all three plots using the helper function
    for data, avg, title, label in plot_configs:
        save_path = os.path.join(dut.raw_data_dir, f"Chan{readback_chan}_"
                                 f"{label}_Stability.png")
        _save_stability_plot(
            data=data,
            avg=avg,
            target=setpoint,
            tolerance=tolerance,
            title=title,
            label=label,
            save_path=save_path,
            ctx=ctx
        )

    # Define the configurations for the three plots
    plot_configs = [
        (loopback_rb,  loopback_rb_avg,  "Loopback", "Loopback"),
        (dcct1_rb, dcct1_rb_avg, "DCCT 1",   "DCCT1"),
        (dcct2_rb, dcct2_rb_avg, "DCCT 2",   "DCCT2")
    ]

    # 1. Generate and save the physical PNG files
    for data, avg, title, label in plot_configs:
        save_path = os.path.join(dut.raw_data_dir, f"Chan{readback_chan}_"
                                 f"{label}_Stability.png")
        _save_stability_plot(
            data=data, avg=avg, target=setpoint, tolerance=tolerance,
            title=title, label=label, save_path=save_path, ctx=ctx
        )

    # 2. Add content to the ReportLab PDF section
    section.append(PageBreak())

    # Define the title style
    paragraph_style = ParagraphStyle(
        "CustomTitle",
        parent=ctx.styles["Normal"],
        fontName="Helvetica",
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
    )

    section.append(Paragraph(f"Power Supply Regulation for Channel "
                             f"{chan}:", paragraph_style))
    section.append(Spacer(1, 0.2 * inch))

    # This is the "Title Loop" fix:
    # Use the same 'label' keys to pull the images into the PDF
    for _, _, _, label in plot_configs:
        img_path = os.path.join(dut.raw_data_dir, f"Chan{readback_chan}"
                                f"_{label}_Stability.png")
        section.append(Image(img_path, 7 * inch, 3 * inch))
        section.append(Spacer(1, 0.1 * inch))


def _save_stability_plot(data, avg, target, tolerance, title, label,
                         save_path, ctx):
    """Helper to generate and save the stability and histogram plots."""
    f = plt.figure(figsize=(8, 4))
    gs = GridSpec(1, 3, figure=f)
    ax1 = f.add_subplot(gs[0, 0:2])
    ax2 = f.add_subplot(gs[0, 2])

    # Stability Plot
    ax1.plot(data)
    ax1.grid(True)
    ax1.set_xlabel("Samples")
    ax1.set_ylabel("(Reading - Average) (mA)")
    ax1.set_title(f"{title} Stability (setpoint={target}A)")

    # Stats Box
    message_str = f"{label} Avg: {round(avg, 5)}A"
    ax1.text(0.02, 0.97, message_str, transform=ax1.transAxes,
             fontsize=10, verticalalignment="top", bbox=ctx.theme.props)

    # Pass/Fail Logic
    # Loopback is positive (avg - target), DCCTs are negative (avg + target)
    err = abs(avg - target) if "Loopback" in label else abs(avg + target)

    tol_ma = tolerance * 1000
    is_pass = err < tolerance
    status = "PASS" if is_pass else "FAIL"
    theme = ctx.theme.good if is_pass else ctx.theme.bad

    test_str = f"Test: |Avg-setpoint| < {tol_ma:.0f}mA?  {status}"
    ax1.text(0.5, 0.07, test_str, transform=ax1.transAxes,
             fontsize=10, verticalalignment="top", ha="center", bbox=theme)

    # Histogram
    ax2.hist(data, bins=20, color="blue", edgecolor="black")
    ax2.grid(True)
    ax2.set_xlabel("Dev. from Avg (mA)")
    ax2.set_title(f"{label} Deviation")

    plt.tight_layout()
    f.savefig(save_path)
    plt.close(f)

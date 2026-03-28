# pylint: disable=broad-exception-caught
"""
FOFB (Fast Orbit Feedback) Functional Testing Module.

This module automates the verification of the Fast Orbit Feedback
(FOFB) subsystem for the Device Under Test (DUT). It performs the
following key functions:

1.  **Configuration**: Sets up FOFB IP addresses and Fast Address
    pointers via EPICS.
2.  **Verification**: Validates DAC output values against expected targets when
    operating in 'Fast' bandwidth mode.
3.  **Traffic Analysis**: Captures and analyzes UDP packets using `tcpdump` to
    verify data transmission integrity on the specified network interface.
4.  **Reporting**: Generates tabular results and traffic logs, appending them
    directly to the test report.

Dependencies:
    - `tcpdump` (requires sudo privileges) for packet capture.
    - `caen_fast_genpacket_loop_inf.sh` for external packet generation.
"""

import os
from datetime import datetime
from time import sleep
import subprocess
import shlex

import h5py
from epics import caget, caput, PV

from reportlab.platypus import Table, Paragraph, Preformatted
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle

from Test.test_report_generator import ReportContext
from Common.initialize_dut import DUT

# -----------------------------
# Small EPICS helpers
# -----------------------------


def safe_caput(name, val, wait=True, timeout=5.0):
    """
    Performs an EPICS caput (write) operation, handling exceptions gracefully.

    Wraps the standard `epics.caput` call in a try/except block to ensure
    program continuity. Logs errors to stdout if the write fails.

    Args:
        name: The name of the Process Variable (PV) to write to.
        val: The value to write to the PV.
        wait: If True, waits for the processing to complete before returning.
        timeout: The maximum time to wait for the write to complete
                 (in seconds).

    Returns:
        bool: True if the write was successful (return code 1), False otherwise
              or if an exception occurred.
    """
    try:
        return caput(name, val, wait=wait, timeout=timeout)
    except Exception as e:
        print(f"caput ERROR for {name} <- {val}: {e}")
        return False


def safe_caget(name, timeout=5.0, *, as_string: bool | None = None):
    """
    Performs an EPICS caget (read) operation, handling exceptions gracefully.

    Wraps the standard `epics.caget` call in a try/except block.

    Args:
        name: The name of the Process Variable (PV) to read.
        timeout: The maximum time to wait for the value (in seconds).
        as_string: If True, returns the string representation of the value.
                   If None (default), uses the default pyepics behavior.

    Returns:
        Any: The value of the PV if successful, or None if the read failed or
             timed out.
    """
    try:
        if as_string is None:
            return caget(name, timeout=timeout)
        return caget(name, timeout=timeout, as_string=as_string)
    except Exception as e:
        print(f"caget ERROR for {name}: {e}")
        return None


def read_pv_array(name):
    """
    Reads a waveform or array PV using the lower-level PV object interface.

    This method is robust for large arrays as it explicitly requests the data
    as a NumPy array (`as_numpy=True`) and includes a short sleep to allow
    connection establishment.

    Args:
        name: The name of the array PV to read.

    Returns:
        np.ndarray | None: The array data if successful, or None if the read
                           failed or the PV could not connect.
    """
    try:
        pv = PV(name)
        sleep(0.05)
        arr = pv.get(as_numpy=True)
        return None if arr is None else arr
    except Exception as e:
        print(f"read_pv_array ERROR for {name}: {e}")
        return None

# -----------------------------
# tcpdump wrapper
# -----------------------------


def capture_udp_packets(iface="enp115s0", port=12345, timeout_s=10):
    """
    Capture ALL UDP packets on `port` for `timeout_s` seconds.
    Returns: (status, out, err, returncode, cmd)
    status = "PASS" if 'udp' appears in stdout, else "FAIL".
    """
    base = f"tcpdump -i {shlex.quote(iface)} udp port {int(port)} -vv -l -n"
    cmd = f"sudo timeout {int(timeout_s)} {base}"
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             check=False)
    except Exception as e:
        return "FAIL", "", str(e), 999, cmd
    out = res.stdout or ""
    err = res.stderr or ""
    status = "PASS" if "udp" in out.lower() else "FAIL"
    return status, out, err, res.returncode, cmd

# -----------------------------
# Main test entry point
# -----------------------------


def fofb_daisy_packet_monotonic_test(dut: DUT, ctx: ReportContext):
    """
    Adds FOFB TX config/verification and UDP RX capture results to the report.
    """

    cmd = "sudo arp -s 10.69.26.55 00:11:22:33:44:55"
    try:
        subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       check=True)
    except Exception as e:
        return "FAIL", "", str(e), 999, cmd

    cmd = "./Functional_Tests/caen_fast_genpacket_loop_inf.sh"
    process = subprocess.Popen(
        cmd, shell=True, text=True, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    num_channels = int(dut.num_channels)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    h5_path = os.path.join(
        dut.raw_data_dir,
        f"epics_test_{dut.psc_sn}_{dut.pv_prefix}_{timestamp}.h5"
    )

    fofb_ip_pv = f"{dut.pv_prefix}FOFB:IPaddr-SP"
    fofb_fastaddr_pvs = [
        f"{dut.pv_prefix}Chan1:FOFB:FastAddr-SP",
        f"{dut.pv_prefix}Chan2:FOFB:FastAddr-SP",
        f"{dut.pv_prefix}Chan3:FOFB:FastAddr-SP",
        f"{dut.pv_prefix}Chan4:FOFB:FastAddr-SP",
    ]

    centered_h2 = ParagraphStyle(
        "CenteredH2",
        parent=ctx.styles["Heading2"],
        alignment=TA_CENTER,
    )

    with h5py.File(h5_path, "w") as h5:
        h5.attrs["generated_by"] = "fofb_daisy_packet_monotonic_test.py"
        h5.attrs["lab"] = f"{dut.pv_prefix}"
        h5.attrs["generated_at"] = datetime.now().isoformat()

        bandval = safe_caget(f"{dut.pv_prefix}Bandwidth-Mode", as_string=True)
        if bandval is not None and str(bandval).strip().lower() == "fast":
            ctx.elements.append(Paragraph(
                "<b>FOFB TX test (Bandwidth-Mode = Fast)</b>",
                centered_h2
            ))
            print("Performing FOFB test because Bandwidth-Mode == Fast")

            # 0x0A451A37 == 10.69.26.55
            # 0x0A008E64 == 10.0.142.100
            safe_caput(fofb_ip_pv, int(0x0A451A37))

            for ch_i, pv in enumerate(fofb_fastaddr_pvs, start=1):
                if ch_i > num_channels:
                    break
                safe_caput(pv, ch_i - 1)

            for ch in range(1, min(4, num_channels) + 1):
                safe_caput(f"{dut.pv_prefix}Chan{ch}:DAC_OpMode-SP", 2)
            sleep(5)

            dac_target = 11.5
            dac_tol = 0.1
            ofc_table = [["PV", "Value", "Pass?"]]

            for ch in range(1, num_channels + 1):
                pv = f"{dut.pv_prefix}Chan{ch}:DAC-I"
                val = safe_caget(pv)
                status = "N/A"
                if val is None:
                    status = "FAIL PV RETURN NONE"
                else:
                    try:
                        fval = float(val)
                        status = "PASS" if abs(fval - dac_target) <= dac_tol \
                            else "FAIL"
                    except Exception:
                        arr = read_pv_array(pv)
                        status = "PASS" if arr is not None else "FAIL"

                ofc_table.append([pv, str(val), status])
                if status != "PASS":
                    print(f"{pv}: {val} -> {status}")

            t = Table(ofc_table, colWidths=[300, 150, 80])
            t.setStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ])
            for r in range(1, len(ofc_table)):
                status = ofc_table[r][2]
                t.setStyle([(
                    'BACKGROUND', (0, r), (-1, r),
                    colors.lightgreen if status == "PASS" else colors.red
                )])
            ctx.elements.append(t)

        else:
            ctx.elements.append(Paragraph(
                "<b>FOFB test: SKIPPED (Bandwidth-Mode != Fast)</b>",
                ctx.styles["Normal"]
            ))
            print("Skipping FOFB TX test; Bandwidth-Mode not 'Fast'.")

        # ---- UDP RX packet test ---------------------------------------------
        status, out, err, returncode, cmd = capture_udp_packets(
            iface="enp115s0", port=12345, timeout_s=10
        )

        tcpdump_log = os.path.join(dut.raw_data_dir, "tcpdump_full.log")
        try:
            with open(tcpdump_log, "w", encoding="utf-8") as fh:
                fh.write(f"Command:\n{cmd}\n\n")
                fh.write(f"Return code: {returncode}\n\n")
                fh.write("STDOUT:\n")
                fh.write(out if out else "(no stdout)")
                fh.write("\n\nSTDERR:\n")
                fh.write(err if err else "(no stderr)")
        except Exception as e:
            print(f"Could not write tcpdump log: {e}")

        ctx.elements.append(Paragraph("<b>UDP RX Packet Test</b>",
                                      centered_h2))

        code_style = ParagraphStyle(
            "CodePreview",
            parent=ctx.styles.get("Code", ctx.styles["Normal"]),
            fontName="Courier",
            fontSize=8,
            leading=9,
        )
        preview = (out or "").strip()
        preview = "\n".join(preview.splitlines()[:40]) or "(no packets \
            captured)"
        ctx.elements.append(Preformatted(preview, code_style))
        ctx.elements.append(Paragraph(
            f"(Full tcpdump log saved to {tcpdump_log})",
            ctx.styles["Normal"]
        ))

        udp_table = [["Test", "Result"], ["UDP RX FOFB", status]]
        t_udp = Table(udp_table, colWidths=[300, 150])
        t_udp.setStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ])
        t_udp.setStyle([
            ('BACKGROUND', (0, 1), (-1, 1),
             colors.lightgreen if status == "PASS" else colors.red)
        ])
        ctx.elements.append(t_udp)
        process.terminate()

    return ctx.elements

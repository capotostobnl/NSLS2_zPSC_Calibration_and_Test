"""
PSC Calibration Module
This module loads values for QSPI flash, and calculates required gains and
offsets to calibrate PSC ADCs and DACs using external traceable calibrated
instruments and reference standards. 
"""
import sys
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# flake8: noqa: E402
# pylint: disable=wrong-import-position
###############################################################################
#   Add outer directory to path, so app can find common dir when run standalone
if __name__ == "__main__":

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
###############################################################################
from instrument_modules.hp3458a_prologix import HP3458A
from instrument_modules.instrument_addresses import DMM_PORT, DMM_BAUD, \
     DMM_GPIB_ADDR, ATE_PREFIX
from common.initialize_dut import DUT
from common.epics_adapters.ate_epics import ATE

#  Formatting Constants for tables
HEAD_FMT = "{:>38}{:>14}{:>14}{:>14}"
DATA_FMT = "{:<29}{:>9.6f}{:>14.6f}{:>14.6f}{:>14.6f}"
VAL_FMT  = "{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}{:>14.6f}"

def save_report_with_reportlab(txt_path, pdf_path):
    """Converts report to PDF with a guaranteed page break and footer placement."""
    
    font_path = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"
    try:
        pdfmetrics.registerFont(TTFont('LibMono', font_path))
        font_name = 'LibMono'
    except:
        font_name = 'Courier'

    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    # Adjusted start_y to 750 (approx 0.5" margin) so it's not "too high"
    start_y = 750
    line_height = 12
    y_position = start_y

    with open(txt_path, "r", encoding="utf-8") as f:
        # Read the entire file content to handle cross-line Form Feeds
        content = f.read()
        
    # Split the document into pages based on the \f character
    pages = content.split('\f')

    for page_index, page_content in enumerate(pages):
        c.setFont(font_name, 10)
        y_position = start_y
        
        lines = page_content.splitlines()
        
        for line in lines:
            # Detect the footer line
            if "Page " in line and " of " in line:
                # Force footer to a safe spot (1 inch from bottom)
                c.drawString(50, 72, line.strip())
                # Don't change y_position here; keep it for the next potential line
            else:
                # Normal line drawing
                c.drawString(50, y_position, line.rstrip())
                y_position -= line_height

            # Emergency page break if text is too long for the page
            if y_position < 90:
                # (Optional: print a warning to console if this happens)
                pass

        # If there are more pages to come, finalize this one and start a new one
        if page_index < len(pages) - 1:
            c.showPage()

    c.save()

if __name__ == "__main__":
    # 1. Define the exact directory where your reports live
    report_dir = "/home/pstester/MikeDevEnv/NSLS2_zPSC_Calibration_and_Test/cal_reports"
    
    # 2. Define the report name (without the extension)
    report_name = "C29-ARI-SXN0014_03-30-26_13-41"
    
    # 3. Construct the full path to the .doc (the "text" source)
    # This results in: /home/.../cal_reports/PSC-4CH-HSF-EIC_0001_05-10-26_20-29.doc
    input_file = os.path.join(report_dir, f"{report_name}.doc")
    
    # 4. Construct the output path for the PDF
    output_pdf = os.path.join(report_dir, f"{report_name}.pdf")

    # Double check if the file actually exists before trying to open it
    if os.path.exists(input_file):
        print(f"Source file found: {input_file}")
        print("Converting 'text-based .doc' to PDF...")
        
        # Pass the .doc path as the text source
        save_report_with_reportlab(input_file, output_pdf)
        
        print(f"Success! PDF created at: {output_pdf}")
    else:
        print(f"File Not Found Error: The script looked for {input_file} but couldn't find it.")
        print("Please check that the filename and directory match exactly.")
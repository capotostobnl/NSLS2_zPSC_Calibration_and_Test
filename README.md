# NSLS-II zPSC Calibration and Functional Test Suite

A comprehensive software suite for the automated calibration and functional verification of Power Supply Controllers (PSC).

## Project Overview

This application provides a unified interface to calibrate and test PSC units. It utilizes EPICS (Experimental Physics and Industrial Control System) to interface with hardware, captures high-precision measurements via HP 3458A DMMs, and generates comprehensive PDF reports.

### Key Features
* **Unified Launcher:** A single entry point for selecting execution modes (Calibration, Functional Testing, or both).
* **Hardware Discovery:** Automatically queries PSC EEPROM settings (channels, resolution, bandwidth) to prevent configuration errors.
* **Intelligent Directory Management:** Dynamically creates reporting and data folders only when required.

---

## Setup and Installation

### 1. Prerequisites
* **Python:** Version 3.11 or higher.
* **EPICS:** The EPICS IOCs for both the ATE and the PSC **must** be actively running on the network.

### 2. Dependencies
Install the required Python packages via pip:
```bash
pip install -r Common/requirements.txt
```
*(Note: Ensure your `requirements.txt` is updated and present in the project)*

### 3. FOFB SFP Testing Compilation
If you are testing the Fast PSC's FOFB SFPs, you must compile the `caen_fast_genpacket.c` application in place. This executable binary is called by the shell script wrapper, which is subsequently called by the `fofb_test.py` module.

---

## Usage

### 1. Hardware Initialization
Before launching the software, verify the physical test stand setup:
* Connect the DCCT Cable and the Channel 1/2/3/4 BPC cables to the ATE.
* Verify the SD card is installed, properly configured with the correct IP Address, and that the EEPROM has been initialized via the front USB port.
* Ensure the correct tuning boards are populated in the ATE.

### 2. Launching the Suite
Run the main launcher from the project root. (The application is fully portable and dynamically resolves file paths using `os.path.abspath(__file__)`, so it can be run from any directory location).
```bash
python launcher.py
```

### 3. Execution Modes
Upon launching, you will be prompted to select a mode:
* **Calibrate Only:** Executes high-precision DAC/ADC calibration.
* **Test Only:** Runs functional verification, including Ramp Tracking, Step Response, and Stability tests.
* **Calibrate and Test:** Performs full end-to-end verification.

### 4. Data Output
Generated reports and logs are saved dynamically to their respective target directories (e.g., `Cal/Calibration_Data` or `Test_Data`). The system utilizes the following naming convention for PDF reports:
`Calibration_[Model]_SN[Serial]_[Timestamp].pdf`

---

## Architecture Notes

### The DUT (Device Under Test) Object
Located in `Common/initialize_dut.py`, the `DUT` class acts as the centralized session manager and state handler for the entire application. 
* **Session Persistence:** Operator inputs (such as Serial Number and network details) are captured once upon instantiation and shared across all active sub-modules.
* **Dynamic Pathing:** It utilizes Python `@property` decorators for attributes like `cal_report_dir` and `test_report_dir`. This "lazy instantiation" ensures that empty directories are not created unless a test actually runs and generates a report.

### Shared Infrastructure (`/Common`)
The `/Common` directory houses the foundational modules and configurations required by both the testing and calibration routines:
* **`initialize_dut.py`:** Instantiates the core `DUT` object.
* **`psc_models.py`:** A data class serving as a registry of PSC hardware specifications, test toggles, and tolerances.

### EPICS Communication Layer
All EPICS communication is abstracted into wrappers located in `/Common/EPICS_Adapters/`:
* **`ate_epics.py`:** A driver dedicated to interacting with the ATE Tester IOC.
* **`psc_epics.py`:** A driver dedicated to interacting with the PSC IOC.

### Calibration Logic
The calibration routine (`psc_calibration.py`) computes correction constants using linear analysis ($y = mx + b$). These constants are derived from high-precision DMM measurements and are written directly to the PSC's internal registers via the EPICS adapter layer.

---

## The PSC Model Registry (`psc_models.py`) Configuration Guide

The `psc_models.py` module reconciles hardware constants required for calibration with the behavioral parameters required for functional verification.

To support the wide variety of symmetric and asymmetric PSC units (such as 2-Channel, 4-Channel, and specialized custom-wired boards), the registry relies heavily on the `ChannelValues` wrapper. `ChannelValues(ch1=x, ch2=y, ...)` allows parameters to be mapped individually to physical channels.

Below is an in-depth breakdown of the configuration parameters available when defining a new `PSCModel`.

### 1. Base Hardware Identity Parameters
These parameters define how the system recognizes and interacts with the unit.
* **`model_id`**: *(str)* The unique internal identifier for the unit type (e.g., `"AR-QD-QF"`).
* **`display_name`**: *(str)* The short, human-readable name used for console menus (e.g., `"2CH-HSS-AR-QD-QF"`).
* **`description`**: *(str)* The full hardware string used for report generation.
* **`designation`**: *(str)* A specific string historically used by calibration scripts to match legacy configurations.
* **`channels`**: *(tuple)* A tuple defining the physical channels present on the board (e.g., `(1, 2)` or `(1, 2, 3, 4)`).
* **`drive_channels` & `readback_channels`**: *(tuple)* These define the hardware routing logic. For a standard 4-channel PSC, this is simply `(1, 2, 3, 4)`. However, for specialized units where one PID loop drives another output (e.g., Channel 3 driving Channel 4), you can remap them: `drive_channels=(2, 3, 3)` mapped to `readback_channels=(2, 3, 4)`.

### 2. Functional Test Selection (`FuncSuite`)
Using the `func_tests` attribute, you can dynamically enable or disable specific tests globally, or on a per-channel basis.
* **`regulation`**: Runs the steady-state regulation check. *(Accepts `True`/`False` or a `ChannelValues` boolean map)*.
* **`smooth`**: Runs the smooth-ramp tracking check. *(Accepts `True`/`False` or a `ChannelValues` boolean map)*.
* **`jump`**: Runs the transient step-response jump test. *(Accepts `True`/`False` or a `ChannelValues` boolean map)*.

### 3. Calibration & Safety Parameters
Hardware-specific constants required to safely power and calibrate the PSC.
* **`CalibrationParameters`**:
  * `ndcct`: *(float)* Normalization factor for the DCCT scaling (e.g., 1000.0 or 2000.0).
  * `burden_resistors`: *(ChannelValues)* The exact resistance values (in Ohms) installed on each channel.
  * `ovc1_threshold` / `ovc2_threshold`: *(ChannelValues)* Primary and secondary over-current trip limits (Amps).
  * `ovv_threshold`: *(ChannelValues)* Over-voltage trip limits (Volts).
* **`PSCScaleFactors`**:
  * `sf_vout`: *(ChannelValues)* Per-channel V/V scaling factors for output voltage monitoring.
  * `sf_spare`: *(ChannelValues)* Per-channel scaling for auxiliary/spare analog inputs.
  * `sf_ramp_rate`, `sf_ignd`, `sf_regulator`, `sf_error`: *(floats)* Mathematical constants used to convert raw EPICS register values into engineering units (Amps, Volts, Amps/sec) for data analysis.

### 4. Functional Test Target Parameters
These nested dataclasses define the exact target limits and criteria the unit must pass during functional testing.

#### `RegulatorTestParams` (Assigned to `reg`)
Evaluates the stability and accuracy of a PSC channel over a fixed duration.
* **`setpoints`**: *(ChannelValues)* The target steady-state current (Amps) to hold.
* **`settling_time`**: *(float)* Delay (seconds) to wait after applying the setpoint before data collection begins. Default is `10`.
* **`tolerance`**: *(float)* Maximum allowable deviation (Amps) between the measured average and the target setpoint for a PASS result. Default is `0.050` (50mA).
* **`ramp_rate`**: *(float)* The slew rate (Amps/second) used to reach the target setpoint.

#### `SmoothRampTestParams` (Assigned to `smooth`)
Validates that the PSC can seamlessly transition between two setpoints at a controlled rate without regulation tracking errors.
* **`start_setpoints`**: *(ChannelValues)* The baseline current (Amps) to begin the ramp.
* **`end_setpoints`**: *(ChannelValues)* The target current (Amps) to reach at the end of the ramp.
* **`ramp_rate`**: *(ChannelValues)* The specific slew rate (Amps/second) for each channel to use during the move.
* **`settling_time`**: *(float)* Extra buffer time added to the calculated ramp duration to ensure the entire waveform finishes before extraction.
* **`tolerance`**: *(float)* Allowable deviation for the ground leakage verification during the ramp.

#### `JumpTestParams` (Assigned to `jump`)
Evaluates control loop stability (overshoot, ringing, settling) during a sudden, instantaneous step change.
* **`start_setpoints`**: *(ChannelValues)* The steady-state baseline current before the jump is injected.
* **`step_size`**: *(ChannelValues)* The magnitude of the instantaneous step (Amps) injected into the loop.
* **`sample_window`**: *(int)* The number of waveform points to extract before and after the step edge to plot the transient response. Default is `500`.
* **`tolerance`**: *(float)* Pass/fail limit for general ground current during the step.

#### `WaveformFlags` (Optional mask for Jump/Smooth tests)
Both `SmoothRampTestParams` and `JumpTestParams` support an optional `waveforms` attribute. By passing a `ChannelValues` map of `WaveformFlags`, you can selectively disable the plotting/checking of specific waveform buffers (e.g., `DAC=False`, `IGND=False`) on a per-channel basis for boards that lack specific monitoring outputs.

---

## Directory Structure

```text
NSLS-II_PSC_CAL_AND_TEST/
├── launcher.py             # Main entry point for the application
├── Cal/                    # Calibration-specific logic and reports
|   ├── psc_calibration_temp.doc  # Temporary calibration document
│   └── psc_calibration.py  # Primary calibration orchestration
├── Cal_Reports/            # Generated calibration reports will go here
├── Common/                 # Shared utilities and hardware definitions
│   ├── initialize_dut.py   # DUT class (Session management & Path anchoring)
│   ├── psc_models.py       # Registry of PSC hardware specifications
│   └── EPICS_Adapters/     # Low-level EPICS communication layers
│       ├── ate_epics.py    # Driver: Adapter for ATE Tester IOC
│       └── psc_epics.py    # Driver: Adapter for PSC IOC 
├── Test/                   # Functional verification suite
│   ├── test_main.py        # Primary test orchestration
│   ├── test_report_generator.py # PDF report generation utilities
│   ├── ate_init.py         # ATE initialization sequence
│   └── Functional_Tests/   # Specific test modules
│       ├── ate_fault_tests.py              # Hardware Interlock Validation
│       ├── evr_timing_test.py              # EVR 1Hz Timestamp check
│       ├── fofb_test.py                    # FOFB Integration (UDP capture & HDF5)
│       ├── jump_test.py                    # Transient Response Analysis
│       ├── ps_regulation_test.py           # DAC Loopback & Regulation verification
│       ├── smooth_ramp_test.py             # Ramp Tracking & Stability Analysis
│       ├── caen_fast_genpacket.c           # Low-level UDP packet generator (C)
│       └── caen_fast_genpacket_loop_inf.sh # Shell wrapper for packet generation
├── Test_Data/              # Functional Test Data and Reports Directory
├── .gitignore              # Git ignore rules
└── README.md               # This file
```
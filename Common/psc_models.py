"""
PSC Model Definitions and Selection Utilities.

This module defines the `PSCModel` dataclass, which serves as the Single Source
of Truth (SSOT) for the Power Supply Controller (PSC) software suite. It reconciles
hardware-specific constants required for calibration with behavioral parameters
required for functional verification.

Key Components:
    - PSCModel: The primary configuration object encapsulating all physical and
      operational parameters for a specific device version.
    - ChannelValues: A flexible data container mapping settings to 2 or 4 physical
      channels.
    - TestParams: Nested dataclasses (Regulator, SmoothRamp, Jump) that define
      pass/fail criteria for automated testing.

Usage:
    This module is intended to be imported by both the Calibration script (cal_main.py)
    and the Functional Test script (test_main.py) to ensure consistent device
    definitions across the project lifecycle.
"""
# flake8: noqa: E501
# pylint: disable=line-too-long

import sys
from dataclasses import dataclass, field
from typing import List, NamedTuple, TypeVar, Generic

T = TypeVar('T')
    
@dataclass(frozen=True)
class ChannelValues(Generic[T]):
    """
    A generic, immutable data container mapping configuration values to physical PSC channels.

    This dataclass ensures type safety and consistency when defining parameters 
    (like tolerances, setpoints, or boolean flags) across 2-channel or 4-channel 
    power supply controllers. 

    Attributes:
        ch1 (T): The configuration value applied to Channel 1.
        ch2 (T): The configuration value applied to Channel 2.
        ch3 (T | None, optional): The configuration value applied to Channel 3. Defaults to None.
        ch4 (T | None, optional): The configuration value applied to Channel 4. Defaults to None.
    """
    ch1: T
    ch2: T
    ch3: T | None = None
    ch4: T | None = None

    def as_list(self, num_chan: int | None = None) -> List[T]:
        """
        Returns the values as a list.
        
        Args:
            num_chan: If provided, returns exactly this many elements.
                     If an element is None, it returns a default (0.0 or T's zero-value).
                     If None, returns only the existing non-None values.
        """
        # Internal helper to handle None values when a specific length is forced
        def safe_val(val):
            if val is not None:
                return val
            # Return a sensible default based on the type of ch1 if possible
            return type(self.ch1)() if self.ch1 is not None else None

        if num_chan is not None:
            full_map = [self.ch1, self.ch2, self.ch3, self.ch4]
            return [safe_val(v) for v in full_map[:num_chan]]

        # Original logic for backward compatibility
        vals = [self.ch1, self.ch2]
        if self.ch3 is not None:
            vals.append(self.ch3)
        if self.ch4 is not None:
            vals.append(self.ch4)
        return vals

    def get(self, index: int, num_chan: int | None = None) -> T:
        """Retrieves value by 0-based index using the sized list."""
        return self.as_list(num_chan)[index]

@dataclass(frozen=True)
class RegulatorTestParams:
    """
        Encapsulates configuration parameters for the Power Supply
        Regulation test.

        This class defines the target setpoints, timing, and acceptance
        criteria used to evaluate the stability and accuracy of a PSC
        channel over a fixed duration.

        Attributes:
            setpoints: A ChannelValues instance mapping specific current
                setpoints (Amps) to each physical channel.
            settling_time: The duration (seconds) to wait after applying the
                setpoint before beginning data collection.
            tolerance: The maximum allowable deviation (Amps) between the
                measured average and the setpoint for a 'PASS' result.
            ramp_rate: The slew rate (Amps/second) at which the PSC should
                transition to the target setpoint.
            num_samples: The total number of data points to capture during
                the regulation stability window.
            sample_interval: The time delay (seconds) between successive
                register reads during data collection.
        """
    setpoints: ChannelValues  # Set Regulator Test Current SP
    settling_time: float = 10  # Default settling time of 10 seconds
    tolerance: float = 0.050  # Default Pass/Fail Threshold to 50mA
    ramp_rate: float = 10  # Default to 10A/s
    num_samples: int = 180  # Total number of data points to collect
    sample_interval: float = 0.3  # Default 300ms between samples


class WaveformFlags(NamedTuple):
    """Masking waveforms for specialized tests/units"""
    DAC: bool = True
    DCCT1: bool = True
    DCCT2: bool = True
    ERROR: bool = True
    REG: bool = True
    VOLT: bool = True
    IGND: bool = True
    SPARE: bool = True

@dataclass(frozen=True)
class SmoothRampTestParams:
    """
    Encapsulates configuration parameters for the Smooth Ramp Test.

    Validates that the PSC can transition between a 'Start' and 'End'
    setpoint at a specific rate without regulation errors.

    Attributes:
        start_setpoints: The starting current (Amps) for the ramp.
        end_setpoints: The target current (Amps) to reach.
        ramp_rate: The slew rate (Amps/second) for the move.
        settling_time: Extra buffer time (seconds) to wait after the
            calculated ramp duration to ensure the waveform is captured.
        tolerance: The allowable deviation (Amps) for ground current checks.
    """

    start_setpoints: ChannelValues  # Set START current for the ramp test
    end_setpoints: ChannelValues  # Set the END current for the ramp test
    ramp_rate: ChannelValues  # Set Per-Channel Ramp Rates for Smooth Test
    settling_time: float = 10  # Default settling time of 10 seconds
    tolerance: float = 0.050  # Default Pass/Fail Threshold to 50mA
    waveforms: ChannelValues[WaveformFlags] = field(default_factory=lambda: ChannelValues(
                                                                        ch1=WaveformFlags(),
                                                                        ch2=WaveformFlags()
                                                                        )
                                                    )

@dataclass
class CalibrationParameters:
    """
    Encapsulates the core hardware constants and logic parameters for PSC calibration.

    This class serves as the primary data container for the physical properties 
    of the Power Supply Controller (PSC) and the specific settings required 
    to orchestrate the calibration sequence.

    Attributes:
        ndcct (float): The normalization factor for the DC Current Transformer (DCCT) 
            Scaling. This is a fundamental physical constant for the unit.
        burden_resistors (ChannelValues): A mapping of the resistance values (Ohms) 
            for the burden resistors installed on each physical channel.
        ovc1_threshold (ChannelValues): Over-Current 1 trip thresholds for 
            hardware protection across all channels.
        ovc2_threshold (ChannelValues): Over-Current 2 trip thresholds for 
            redundant hardware protection.
        ovv_threshold (ChannelValues): Over-Voltage trip thresholds (Volts) 
            assigned to each physical channel.
        num_runs (int): The total number of calibration iterations to perform per 
            channel to ensure statistical stability. Defaults to 5.
        sp0 (float): The initial setpoint (Amps) used as the baseline 'Low' 
            measurement during the calibration loop.
    """
    ndcct: float
    burden_resistors: ChannelValues
    ovc1_threshold: ChannelValues
    ovc2_threshold: ChannelValues
    ovv_threshold: ChannelValues
    num_runs: int = 5
    sp0: float = 1.0
    current_full_scale_dividend: float = 1.0
    g_target_multiplier: float = 10.0

@dataclass
class CalibrationTestThresholds:
    """Encapsulates all pass/fail limits for PSC calibration."""
    init_error_upper: float = 0.1  # Upper bound of initial error.
    init_dcct_gain_upper: float = 1.008  # Upper bound of DCCT Gain
    init_dcct_gain_lower: float = 1.006  # Lower bound of DCCT Gain
    dac_rb_offset_upper: float = 0.01  # Upper bound of DAC RB Offset
    dac_rb_gain_upper: float = 1.001  # Upper bound of DAC RB Gain
    verif_error_upper: float = 0.1  # Upper bound of Verification Error
    final_offset_upper: float = 0.001  # Upper bound of final measured offsets
    final_gain_upper: float = 1.000050  # Upper bound of final measured gains
    final_gain_lower: float = 0.999950  # Lower bound of final measured gains
    verif_offset_mean_upper: float = 0.001  # Upper bound of final measured offsets mean
    verif_offset_mean_std_dev_upper: float = 0.001  # Upper bound of final measured Std Dev. offsets mean
    verif_gain_mean_upper: float = 1.000050  # Upper bound of final measured gains mean
    verif_gain_mean_lower: float = 0.999950  # Lower bound of final measured gains mean
    verif_gain_std_dev_upper: float = 0.0001  # Upper bound of final measured Std. Dev. gains mean

@dataclass
class PSCFaultThresholdsLimits:
    """
    Defines the hardware protection thresholds and fault latching criteria for the PSC.

    This class centralizes the safety parameters required to protect the magnet 
    load and power supply hardware. It is categorized into two primary 
    functional groups: immediate trip thresholds (triggering an interlock) and 
    fault count limits (defining the sensitivity of the error latching logic).

    Attributes:
        ovc1_threshold (ChannelValues): Primary over-current trip limits (Amps).
        ovc2_threshold (ChannelValues): Secondary redundant over-current trip limits (Amps).
        ovv_threshold (ChannelValues): Over-voltage trip limits (Volts).
        err1_threshold (float): Sensitivity threshold for the primary error amplifier. Defaults to 10.
        err2_threshold (float): Sensitivity threshold for the secondary error amplifier. Defaults to 10.
        ignd_threshold (float): Maximum allowable ground leakage current (Amps) before a fault is declared. Defaults to 10.

        ovc1_flt_cnt (float): Filter time/count for OVC1 detection. Defaults to 0.01.
        ovc2_flt_cnt (float): Filter time/count for OVC2 detection. Defaults to 0.01.
        ovv_flt_cnt (float): Filter time/count for OVV detection. Defaults to 0.01.
        err1_flt_cnt (float): Integration limit for Error 1 faults. Defaults to 0.1.
        err2_flt_cnt (float): Integration limit for Error 2 faults. Defaults to 0.1.
        ignd_flt_cnt (float): Integration limit for ground current faults. Defaults to 0.2.
        dcct_flt_cnt (float): Tolerance window for DCCT-related monitoring faults. Defaults to 0.2.
        flt1_flt_cnt (float): Filter count for internal Fault 1 status. Defaults to 0.1.
        flt2_flt_cnt (float): Filter count for internal Fault 2 status. Defaults to 3.
        flt3_flt_cnt (float): Filter count for internal Spare/Fault 3 status. Defaults to 0.5.
        flt_on_cnt (float): Verification time for the 'Power On' state feedback. Defaults to 3.
        flt_heartbeat_cnt (float): Watchdog timeout for controller-to-gate-driver communication. Defaults to 3.
    """
    # -------------------------------------------------------------------------
    # Fault Thresholds
    # -------------------------------------------------------------------------
    ovc1_threshold: ChannelValues = field(default_factory=lambda: ChannelValues(0, 0))
    ovc2_threshold: ChannelValues = field(default_factory=lambda: ChannelValues(0, 0))
    ovv_threshold: ChannelValues = field(default_factory=lambda: ChannelValues(0, 0))
    err1_threshold: float = 10
    err2_threshold: float = 10
    ignd_threshold: float = 10

    # -------------------------------------------------------------------------
    # Fault Count Limits
    # -------------------------------------------------------------------------
    ovc1_flt_cnt: float = 0.01
    ovc2_flt_cnt: float = 0.01
    ovv_flt_cnt: float = 0.01
    err1_flt_cnt: float = 0.1
    err2_flt_cnt: float = 0.1
    ignd_flt_cnt: float = 0.2
    dcct_flt_cnt: float = 0.2
    flt1_flt_cnt: float = 0.1
    flt2_flt_cnt: float = 3
    flt3_flt_cnt: float = 0.5
    flt_on_cnt: float = 3
    flt_heartbeat_cnt: float = 3

@dataclass
class PSCScaleFactors:
    """
    Defines the mathematical scaling constants for signal conversion and data normalization.

    This class centralizes the multipliers used to convert raw register values into 
    engineering units (Amps, Volts) and defines the coefficients for the control 
    loop's dynamic behavior. It is a critical component for ensuring 
    that the high-energy physics data analyzed in Python aligns with the physical 
    outputs of the Power Supply Controller.

    Attributes:
        current_full_scale_dividend (float): The numerator used in calculating 
            maximum burden current. Defaults to 1.0.
        g_target_multiplier (float): The target multiplier used to determine 
            V/A scaling. Defaults to 10.0.
        sf_ramp_rate (float): The scale factor for slew rate and ramping logic. 
            Defaults to 4.0.
        sf_dcct_scale (float | None): Specific multiplier for DCCT current monitoring. 
            If None, the system dynamically utilizes the p_scale_factor.
        sf_vout (ChannelValues): Per-channel scaling factors for output voltage 
            monitoring.
        sf_ignd (float): Scaling factor for ground leakage current measurements. 
            Defaults to 1.0.
        sf_spare (ChannelValues): Per-channel scaling for auxiliary or "Spare" 
            analog inputs.
        sf_regulator (float): Multiplier for regulator feedback loop analysis. 
            Defaults to 1.0.
        sf_error (float): Scaling factor for error amplifier signal processing. 
            Defaults to 1.0.
    """

    sf_ramp_rate: float = 4.0
    sf_dcct_scale: float | None = None  # Will use p_scale_factor if None
    sf_vout: ChannelValues = field(default_factory=lambda: ChannelValues(0.0, 0.0))
    sf_ignd: float = 1.0
    sf_spare: ChannelValues = field(default_factory=lambda: ChannelValues(0.0, 0.0))
    sf_regulator: float = 1.0
    sf_error: float = 1.0

class PSCCalculator:
    """
    Handles derived mathematical calculations for PSC hardware units.

    This logic class decouples mathematical operations from the static data 
    stored in the PSCModel. By accepting CalibrationParameters as an input, 
    it ensures that scaling factors used in both calibration and verification 
    remain mathematically consistent across the application.

    Methods:
        get_current_full_scale(channel): Calculates the maximum burden current 
            based on the specific channel's resistor value.
        get_s_scale_factor(channel): Derives the Voltage-per-Amp scaling 
            factor (S-Scale) using the burden resistance and target multiplier.
        get_p_scale_factor(channel): Derives the Amp-per-Volt scaling 
            factor (P-Scale) required for power supply control logic.
    """
    def __init__(self, cal_params: CalibrationParameters):
        """
        Initializes the calculator with model-specific calibration constants.

        Args:
            cal_params (CalibrationParameters): The data container holding 
                ndcct, burden resistors, and dividend constants.
        """
        self.params = cal_params

    def get_current_full_scale(self, channel: int) -> float:
        """Calculates Max burden current for a specific channel."""
        rb = getattr(self.params.burden_resistors, f"ch{channel}")
        return self.params.current_full_scale_dividend / rb

    def get_s_scale_factor(self, channel: int) -> float:
        """Calculates V/A scaling factor: Burden * Target Multiplier."""
        rb = getattr(self.params.burden_resistors, f"ch{channel}")
        return rb * self.params.g_target_multiplier

    def get_p_scale_factor(self, channel: int) -> float:
        """Calculates PS scaling factor A/V: ndcct / s_scale_factor."""
        s_scale = self.get_s_scale_factor(channel)
        return self.params.ndcct / s_scale

@dataclass(frozen=True)
class JumpTestParams:
    """
    Configuration for the Jump (Step Response) Test.
    
    Used to evaluate the control loop stability by measuring overshoot, 
    ringing, and settling time during a sudden current step.
    """
    start_setpoints: ChannelValues  # Baseline current before the jump
    step_size: ChannelValues       # The magnitude of the jump (Amps)
    sample_window: int = 500        # Points to show before/after the jump
    tolerance: float = 0.050        # Ground current pass/fail threshold (A)
    waveforms: ChannelValues[WaveformFlags] = field(default_factory=lambda: ChannelValues(
                                                                        ch1=WaveformFlags(),
                                                                        ch2=WaveformFlags()
                                                                        )
                                                    )

@dataclass(frozen=True)
class FuncSuite:
    """
    Select which functional tests each PSC carries out.
    Supports global booleans or per-channel ChannelValues.
    """
    regulation: bool | ChannelValues = True
    jump: bool | ChannelValues = True
    smooth: bool | ChannelValues = True

    def is_enabled(self, test_name: str, chan: int) -> bool:
        """
        Helper to resolve the test status for a specific channel.
        Usage: dut.model.func_tests.is_enabled('regulation', chan)
        """
        val = getattr(self, test_name)

        # If it's a global boolean (e.g., True/False), return it directly
        if isinstance(val, bool):
            return val

        # If it's a ChannelValues object, look up the specific channel
        if isinstance(val, ChannelValues):
            # getattr returns the value (True/False/None).
            # We treat None as False.
            return getattr(val, f"ch{chan}", False) or False

        return False


@dataclass(frozen=True, kw_only = True)
class PSCModel:
    """
    Represents the technical specifications and test limits for a specific
    PSC model.

    Attributes:
        model_id: Unique internal identifier for the unit type (e.g., "R1-HSS").
        display_name: Short name used for console menus and reporting titles.
        description: Full hardware string (e.g., "PSC-2CH-HSS-AR-QD-QF").
        channels: The physical number of channels (2 or 4).
        reg: An instance of RegulatorTestParams defining stability test criteria.
        smooth: An instance of SmoothRampTestParams defining slew rate and range.
        jump: An instance of JumpTestParams defining step response behavior.
    """

    ################################################################################
    #      Common Parameters
    ################################################################################
    model_id: str         # Internal ID (e.g., "R1-HSS")
    display_name: str     # Short name for menu (e.g., "R1 2Ch")
    description: str      # Full description (e.g., "PSC-2CH-HSS-AR-QD-QF")
    channels: tuple[int, ...] = field(default_factory=tuple)  # PSC Channels Used
    designation: str      # Calibration Script Designation

    # Select Functional Tests to perform
    func_tests: FuncSuite = field(default_factory=FuncSuite)

    # drive_channels and readback_channels are special values. They will match the
    # PSC 1:1 for normal PSCs, e.g., drive_channels[1, 2, 3, 4] will match with
    # readback_channels[1, 2, 3, 4]
    # But to address special cases -- e.g. BTA-R3 with wire jumpers
    # added, can use Channel 3's PID loop to drive Channel 4's output.
    # In this case, drive_channels[2, 3, 3] will match with
    # readback_channels[2, 3, 4], where 1 is unused, and Channel 3 drives Channel 4

    drive_channels: tuple[int, ...] = field(default_factory=tuple)
    readback_channels: tuple[int, ...] = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(self, 'channels', tuple(self.channels))
        object.__setattr__(self, 'drive_channels', tuple(self.drive_channels))
        object.__setattr__(self, 'readback_channels', tuple(self.readback_channels))

    ################################################################################
    #      Calibration Parameters
    ################################################################################
    calibration_parameters: CalibrationParameters = field(
        default_factory=CalibrationParameters
    )
    calibration_test_thresholds: CalibrationTestThresholds = field(
        default_factory = CalibrationTestThresholds
    )
    psc_fault_thresholds_limits: PSCFaultThresholdsLimits = field(
        default_factory = PSCFaultThresholdsLimits
    )
    psc_scale_factors: PSCScaleFactors = field(
        default_factory = PSCScaleFactors
    )

    @property
    def calc(self) -> PSCCalculator:
        """Returns a calculator instance"""
        return PSCCalculator(self.calibration_parameters)

    ################################################################################
    #      Test Parameters
    ################################################################################
    reg: RegulatorTestParams  # Regulator Test Parameters Class
    smooth: SmoothRampTestParams  # Smooth Ramp Test Parameters Class
    jump: JumpTestParams  # Jump Test Parameters Class


# Define the Registry of all known units
MODELS = {
    # 2-Channel Units
    "AR-QD-QF": PSCModel(model_id="AR-QD-QF",
                       display_name="2CH-HSS-AR-QD-QF",
                       description="PSC-2CH-HSS-AR-QD-QF",
                       designation="PSC-2CH-HSS-AR-QD-QF_",
                       channels=(1, 2),
                       drive_channels=(1, 2),
                       readback_channels=(1,2),

                       #####################################################################
                       #      Calibration                                                  #
                       #####################################################################
                       calibration_parameters=CalibrationParameters(
                            ndcct=1000.0,
                            burden_resistors=ChannelValues(ch1=18.0, ch2=9.0),
                            ovc1_threshold=ChannelValues(ch1=51.0, ch2=101.0),
                            ovc2_threshold=ChannelValues(ch1=51.0, ch2=101.0),
                            ovv_threshold=ChannelValues(ch1=12.7, ch2=12.7),
                       ),

                       psc_scale_factors=PSCScaleFactors(
                           sf_vout=ChannelValues(ch1=-1.25, ch2=-1.25),
                           sf_spare=ChannelValues(ch1=-6.0, ch2=-12.0),
                       ),
                       #######################################################################
                       #      Test                                                           #
                       #######################################################################
                       reg=RegulatorTestParams(
                           setpoints=(reg_pts := ChannelValues(ch1=30,
                                                   ch2=50)),
                           settling_time=10),


                       smooth=SmoothRampTestParams(
                           start_setpoints=ChannelValues(ch1=0,
                                                         ch2=0,
                                                         ),
                           end_setpoints=ChannelValues(ch1=49.9,
                                                       ch2=99.9,
                                                       ),
                           ramp_rate=ChannelValues(ch1=10,
                                                   ch2=20),
                           settling_time=10,
                           tolerance=0.05),
                       jump=JumpTestParams(
                           start_setpoints=reg_pts,
                           step_size=ChannelValues(ch1=0.05,
                                                   ch2=0.05),
                           sample_window=500,
                           tolerance=0.05
                        )
                       ),

    "ABEND-QFA": PSCModel(model_id="ABEND-QFA",
                          display_name="ABEND QFA - R3 2Ch",
                          description="PSC-2CH-HSS-AR-Abend-QFA",
                          designation="2CH-HSS-AR-ABend-QFA_",
                          channels=(1, 2),
                          drive_channels=(1, 2),
                          readback_channels=(1,2),

                          #####################################################################
                          #      Calibration                                                  #
                          #####################################################################
                          calibration_parameters=CalibrationParameters(
                                ndcct=2000.0,
                                burden_resistors=ChannelValues(ch1=4.5, ch2=9.0),
                                ovc1_threshold=ChannelValues(ch1=390.0, ch2=195.0),
                                ovc2_threshold=ChannelValues(ch1=390.0, ch2=195.0),
                                ovv_threshold=ChannelValues(ch1=470.0, ch2=190.0),
                          ),

                          psc_scale_factors=PSCScaleFactors(
                                sf_vout=ChannelValues(ch1=-47.5, ch2=-20.0),
                                sf_spare=ChannelValues(ch1=-40.0, ch2=-20.0),
                          ),

                          #######################################################################
                          #      Test                                                           #
                          #######################################################################
                          reg=RegulatorTestParams(
                           setpoints=(reg_pts := ChannelValues(ch1=200,
                                                   ch2=100)),
                           settling_time=30),

                          smooth=SmoothRampTestParams(
                              start_setpoints=ChannelValues(ch1=0,
                                                            ch2=0,
                                                            ),
                              end_setpoints=ChannelValues(ch1=385,
                                                          ch2=185,
                                                          ),
                              ramp_rate=ChannelValues(ch1=60,
                                                      ch2=30),
                              settling_time=10,
                              tolerance=0.05),
                          jump=JumpTestParams(
                              start_setpoints=reg_pts,
                              step_size=ChannelValues(ch1=0.5,
                                                      ch2=0.5),
                              sample_window=500,
                              tolerance=0.05
                           )
                          ),

    "SPECIAL_2CH_HSS_AR-Slow-XY-Corr": PSCModel(model_id="AR-Slow-XY-Corr",
                        display_name="4CH-MSS-AR Slow XY Corr",
                        description="PSC-4CH-MSS-AR-Slow XY Corr.",
                        designation="4CH-MSS-AR Slow XY Corr_",
                        channels=(1, 2),
                        drive_channels=(1, 2),
                        readback_channels=(1,2),

                            #######################################################################
                            #      Calibration                                                    #
                            #######################################################################
                            calibration_parameters=CalibrationParameters(
                                    ndcct=1000.0,
                                    burden_resistors=ChannelValues(ch1=33.333333, ch2=33.333333,
                                                ),
                                    ovc1_threshold=ChannelValues(ch1=24.5, ch2=24.5),
                                    ovc2_threshold=ChannelValues(ch1=24.5, ch2=24.5),
                                    ovv_threshold=ChannelValues(ch1=18.5, ch2=18.5),
                            ),

                            psc_scale_factors=PSCScaleFactors(
                                    sf_vout=ChannelValues(ch1=1.9, ch2=1.9),
                                    sf_spare=ChannelValues(ch1=-5.0, ch2=-5.0),
                            ),
                            #######################################################################
                            #      Test                                                           #
                            #######################################################################
                        reg=RegulatorTestParams(
                            setpoints=(reg_pts := ChannelValues(ch1=10,
                                                    ch2=10)),
                            settling_time=10),


                        smooth=SmoothRampTestParams(
                            start_setpoints=ChannelValues(ch1=0,
                                                            ch2=0,
                                                            ),
                            end_setpoints=ChannelValues(ch1=23.9,
                                                        ch2=23.9,
                                                        ),
                            ramp_rate=ChannelValues(ch1=10,
                                                    ch2=10,
                                                    ),
                            settling_time=10,
                            tolerance=0.05),
                        jump=JumpTestParams(
                            start_setpoints=reg_pts,
                            step_size=ChannelValues(ch1=0.05,
                                                    ch2=0.05,
                                                    ),
                            sample_window=500,
                            tolerance=0.05
                            )
                        ),

    # 4-Channel Units
    "C29-ARI-SXN": PSCModel(model_id="C29-ARI-SXN",
                       display_name="C29-ARI-SXN",
                       description="C29-ARI-SXN",
                       designation="C29-ARI-SXN",
                       channels=(1, 2, 3, 4),
                       drive_channels=(1, 2, 3, 4),
                       readback_channels=(1,2, 3, 4),

                          #######################################################################
                          #      Calibration                                                    #
                          #######################################################################
                          calibration_parameters=CalibrationParameters(
                                ndcct=1000.0,
                                burden_resistors=ChannelValues(ch1=83.333333, ch2=83.333333,
                                            ch3=83.333333, ch4=83.333333),
                                ovc1_threshold=ChannelValues(ch1=12, ch2=12, ch3=12, ch4=12),
                                ovc2_threshold=ChannelValues(ch1=24.5, ch2=24.5, ch3=24.5, ch4=24.5),
                                ovv_threshold=ChannelValues(ch1=18.5, ch2=18.5, ch3=18.5, ch4=18.5),
                          ),

                          psc_scale_factors=PSCScaleFactors(
                                sf_vout=ChannelValues(ch1=1.9, ch2=1.9, ch3=1.9, ch4=1.9),
                                sf_spare=ChannelValues(ch1=-5.0, ch2=-5.0, ch3=-5.0, ch4=-5.0),
                          ),
                          #######################################################################
                          #      Test                                                           #
                          #######################################################################
                       reg=RegulatorTestParams(
                           setpoints=(reg_pts := ChannelValues(ch1=5,
                                                   ch2=5,
                                                   ch3=5,
                                                   ch4=5)),
                           settling_time=10),


                       smooth=SmoothRampTestParams(
                           start_setpoints=ChannelValues(ch1=-5,
                                                         ch2=-5,
                                                         ch3=-5,
                                                         ch4=-5),
                           end_setpoints=ChannelValues(ch1=5,
                                                       ch2=5,
                                                       ch3=5,
                                                       ch4=5),
                           ramp_rate=ChannelValues(ch1=10,
                                                   ch2=10,
                                                   ch3=10,
                                                   ch4=10),
                           settling_time=10,
                           tolerance=0.05),
                       jump=JumpTestParams(
                           start_setpoints=reg_pts,
                           step_size=ChannelValues(ch1=0.05,
                                                   ch2=0.05,
                                                   ch3=0.05,
                                                   ch4=0.05),
                           sample_window=500,
                           tolerance=0.05
                        )
                       ),

    "BTA-B8-B5-6": PSCModel(
                                model_id="BTA-B8-B5-6",
                                display_name="4CH-HSS-BTA-B8-B5-6",
                                description="PSC-4CH-HSS-BTA-B8-B5-6",
                                designation="4CH-HSS-BTA-B8-B5-6_",
                                channels=(2, 3, 4),
                                drive_channels=(2, 3, 3),
                                readback_channels=(2, 3, 4),
                                func_tests=FuncSuite(
                                    regulation=ChannelValues(
                                        ch1 = None,
                                        ch2 = True,
                                        ch3 = True,
                                        ch4 = False
                                    ),
                                    jump=True,
                                    smooth=True),


                          #######################################################################
                          #      Calibration                                                    #
                          #######################################################################
                          calibration_parameters=CalibrationParameters(
                          ndcct=2000.0,
                          burden_resistors=ChannelValues(ch1=None, ch2=4.6,
                                                         ch3=5.6, ch4=None),

                          ovc1_threshold=ChannelValues(ch1=None, ch2=390, ch3=325, ch4=None),
                          ovc2_threshold=ChannelValues(ch1=None, ch2=390, ch3=325, ch4=None),
                          ovv_threshold=ChannelValues(ch1=None, ch2=25, ch3=85, ch4=None),
                          ),

                          psc_scale_factors= PSCScaleFactors(
                                sf_vout=ChannelValues(ch1=None, ch2=-2.5, ch3=-8.0, ch4=-8.0),
                                sf_spare=ChannelValues(ch1=None, ch2=-39, ch3=-32.5, ch4=-32.5),
                          ),
                          #######################################################################
                          #      Test                                                           #
                          #######################################################################
                             reg=RegulatorTestParams(
                                setpoints=(reg_pts := ChannelValues(ch1=None,
                                                                    ch2=195,
                                                                    ch3=162.5,
                                                                    ch4=None)),
                                settling_time=10),
                             smooth=SmoothRampTestParams(
                                 start_setpoints=ChannelValues(ch1=None,
                                                               ch2=0,
                                                               ch3=0,
                                                               ch4=None),
                                 end_setpoints=ChannelValues(ch1=None,
                                                             ch2=285,
                                                             ch3=285,
                                                             ch4=None),
                                 ramp_rate=ChannelValues(ch1=None,
                                                         ch2=100,
                                                         ch3=100,
                                                         ch4=None),
                                 settling_time=10,
                                 tolerance=0.05,

                                 waveforms=ChannelValues(
                                     ch1=None,
                                     ch2=WaveformFlags(), # using defaults
                                     ch3=WaveformFlags(), # using defaults
                                     ch4=WaveformFlags(
                                     DAC=False,
                                     DCCT1=False,
                                     DCCT2=False,
                                     ERROR=False,
                                     REG=True,
                                     VOLT=True,
                                     IGND=False,
                                     SPARE=True
                                    )
                                )
                            ),
                             jump=JumpTestParams(
                                 start_setpoints=reg_pts,
                                 step_size=ChannelValues(ch1=0.5,
                                                         ch2=0.5,
                                                         ch3=0.5,
                                                         ch4=0.5),
                                 sample_window=500,
                                 tolerance=0.05,
                                 waveforms=ChannelValues(
                                     ch1=None,
                                     ch2=WaveformFlags(), # using defaults
                                     ch3=WaveformFlags(), # using defaults
                                     ch4=WaveformFlags(
                                     DAC=False,
                                     DCCT1=False,
                                     DCCT2=False,
                                     ERROR=False,
                                     REG=True,
                                     VOLT=True,
                                     IGND=False,
                                     SPARE=True
                                    )
                                )
                              ),
                            ),
}


# -----------------------------------------------------------------------------
# Selection Utility
# -----------------------------------------------------------------------------

def get_psc_model_from_user(num_channels: int) -> PSCModel:
    # Normalize channel count:
    # 2 or less becomes 2; 3 or more becomes 4.
    if num_channels is None:
        # Fallback if the DUT detection failed entirely
        raise RuntimeError("Unable to detect # Of Channels..Check EEPROM?")
    else:
        search_channels = 2 if num_channels <= 2 else 4

    # Filter models based on the normalized count
    if search_channels == 2:
        model_list = [m for m in MODELS.values() if len(m.channels) <= 2]
    else:
        model_list = [m for m in MODELS.values() if len(m.channels) >= 3]

    # Safety check to prevent the ValueError: max() arg is an empty sequence
    if not model_list:
        print(f"\n[!] Error: No models registered for {search_channels} channels.")
        # Optional: fall back to showing ALL models if the filtered list is empty
        # model_list = list(MODELS.values())
        sys.exit(1)

    # Now this will never receive an empty sequence
    max_label_len = max(len(f"'{m.display_name}'") for m in model_list)

    print(f"\nDetected {num_channels} channels. Showing {search_channels}-channel models:")
    print("-" * (max_label_len + 15))
    for i, model in enumerate(model_list, 1):
        print(f"  {i}) {model.display_name.ljust(max_label_len)} [{model.description}]")
    print("-" * (max_label_len + 15))
    # ------------------------
    while True:
        try:
            choice = input("\nEnter Type (or 'q' to quit): ")\
                .strip().lower()

            if choice == 'q':
                print("Testing aborted by operator.")
                sys.exit(0)

            idx = int(choice) - 1
            if 0 <= idx < len(model_list):
                selected = model_list[idx]
                print(f"--> Selected: {selected.display_name}\n")
                return selected

            print(f"Invalid choice. Select 1-{len(model_list)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

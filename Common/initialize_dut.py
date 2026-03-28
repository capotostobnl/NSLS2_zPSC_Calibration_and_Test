"""
DUT setup utilities for NSLS-II PSC automated testing.

This module provides a `DUT` dataclass that:
- Automatically sweeps the network to discover the PSC PV prefix,
  falling back to operator prompts if needed, and prompts for the
  serial number.

- Queries the PSC over EPICS to capture configuration (channels,
  resolution, bandwidth, polarity).

- Creates report directories and a timestamped raw-data subdirectory.
"""
import os
import subprocess
import platform
from datetime import datetime
from dataclasses import dataclass, field
from typing import Tuple
from time import sleep
from Common.EPICS_Adapters.psc_epics import PSC
from Common.psc_models import get_psc_model_from_user, PSCModel


@dataclass
class DUT:
    """Represents the Device Under Test (PSC) and related file paths/state.

        Attributes:
            psc_sn: Zero-padded 4-digit PSC serial number (e.g., '0042').
            pv_prefix: EPICS PV prefix of the PSC (e.g., 'lab{3}').
            psc: EPICS adapter created after pv_prefix is known.
            model: PSCModel dataclass with parameters/limits for
            different models.

            cal_report_dir: Property that creates/returns the calibration
            report path.

            test_report_dir: Property that creates/returns the test
            report path.

            raw_data_dir: Timestamped raw-data subdirectory path for this run.
            num_channels: Number of PSC channels (queried from EPICS).
            resolution: Resolution mode string (queried from EPICS).
            bandwidth: Bandwidth mode string (queried from EPICS).
            polarity: Polarity mode string (queried from EPICS).
            dir_timestamp: Timestamp string used in raw-data directory naming.
        """

    # --- identifiers / adapter ---
    psc_sn: str = ""
    pv_prefix: str = ""
    psc_num: int = field(init=False, default=0)
    psc: PSC | None = None
    model: PSCModel = field(init=False)

    # --- filesystem / run info ---
    # We dynamically find the project root relative to this file
    _project_root: str = field(init=False)
    _data_root: str = field(init=False)

    def __post_init__(self):
        """Initialize project-relative paths after the object is created."""
        # 1. Start at Common/initialize_dut.py
        this_file_path = os.path.abspath(__file__)

        # 2. Go up one level to get to the project root
        self._project_root = os.path.dirname(os.path.dirname(this_file_path))

        # 3. Anchor our data folder to the project root
        self._data_root = os.path.join(self._project_root, "Test_Data")

    @property
    def cal_report_dir(self) -> str:
        """Returns path and creates Cal_Reports ONLY when accessed."""
        path = os.path.join(self._project_root, "Cal_Reports")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def test_report_dir(self) -> str:
        """Returns path and creates Test_Reports ONLY when accessed."""
        path = os.path.join(self._project_root, "Test_Reports")
        os.makedirs(path, exist_ok=True)
        return path

    raw_data_dir: str = field(init=False, default="")
    dir_timestamp: str = field(init=False, default="")

    # --- PSC configuration (populated from EPICS) ---
    num_channels: int = field(init=False, default=2)
    resolution: str = field(init=False, default="")
    bandwidth: str = field(init=False, default="")
    polarity: str = field(init=False, default="")

    # --- operator input ---
    def prompt_inputs(self):
        """Prompt user for basic DUT info.
           - Build the PSC Adapter with that PV prefix
           - Get PSC configuration (PV Values)
           - Create directory structure, timestamps
        """
        self.psc_sn = self._get_psc_sn()
        self.pv_prefix = self._get_psc_pv_prefix()

        # Create the adapter...
        self.psc = PSC(prefix=self.pv_prefix)

        # Populate the configuration from the PSC PVs
        self.query_psc_config()

        # Get PSC Model from psc_models.py Function
        self.model = get_psc_model_from_user(self.num_channels)

        # Raw Logs are created immediately
        raw_logs_root = os.path.join(self._data_root, "Raw_Logs")
        self.raw_data_dir, self.dir_timestamp = \
            self.make_rawdata_subdir(raw_logs_root)

    def query_psc_config(self) -> None:
        """Get values from PSC about unit type from PVs"""
        if self.psc is None:
            raise RuntimeError("PSC adapter not initialized before \n"
                               "calling query_psc_config()")
        self.num_channels = self.psc.get_num_channels()
        self.resolution = self.psc.get_resolution()
        self.bandwidth = self.psc.get_bandwidth()
        self.polarity = self.psc.get_polarity()

        # Test that EEPROM Values aren't Zeroed...
        print("\n\n\n Reading EEPROM...")
        print(f"EEPROM # Of Channels: {self.num_channels}")
        print(f"EEPROM Resolution: {self.resolution}")
        print(f"EEPROM Bandwidth: {self.bandwidth}")
        print(f"EEPROM Polarity: {self.polarity}")
        print("\n\n\n")
        if self.num_channels not in [2, 4]:
            raise ConnectionError("Could not detect valid PSC channels at "
                                  f"{self.pv_prefix}. Check EEPROM is "
                                  "Configured, PSC is connected. ")
        if self.resolution[:2] not in ["HS", "MS"]:
            raise ConnectionError("Could not detect valid PSC at "
                                  f"{self.pv_prefix}. Check EEPROM is "
                                  "Configured, PSC is connected. ")
        if self.bandwidth[:1] not in ["S", "F"]:
            raise ConnectionError("Could not detect valid PSC at "
                                  f"{self.pv_prefix}. Check EEPROM is "
                                  "Configured, PSC is connected. ")
        if self.polarity[:1] not in ["B", "U"]:
            raise ConnectionError("Could not detect valid PSC at "
                                  f"{self.pv_prefix}. Check EEPROM is "
                                  "Configured, PSC is connected. ")

    def make_rawdata_subdir(self, parent_dir: str) -> Tuple[str, str]:
        """Create a timestamped subdir for raw diagnostic data."""
        dir_timestamp = datetime.now().strftime("%m-%d-%y_%H-%M")
        subdir_name = (f"{self.num_channels}ch_{self.resolution[:2]}"
                       f"{self.bandwidth[:1]}_SN{self.psc_sn}_RawData_"
                       f"{dir_timestamp}")

        raw_data_path = os.path.join(parent_dir, subdir_name)
        os.makedirs(raw_data_path, exist_ok=True)
        return raw_data_path, dir_timestamp

    def _get_psc_sn(self) -> str:
        """Prompt for the PSC S/N, add leading zero padding"""
        while True:
            psc_sn = input('\nEnter PSC serial number: (Enter "H" '
                           'for help):')
            # If Help...
            if psc_sn == "H":
                print("Serial Number is on the ITR document"
                      "attached to the PSC Chassis")
                continue

            # Check if a digit was entered and re-prompt if not...
            elif not psc_sn.isdigit():
                print("Serial number must be numeric, "
                      "between 0001 and 9999")
                continue

            # Check if digit between 1 and 9999...
            else:
                psc_sn = int(psc_sn)
                if not 1 <= psc_sn <= 9999:
                    print("Serial number must be numeric, "
                          "between 001 and 9999")
                    continue

            # Add leading zeroes to psc_sn...
            psc_sn = f"{psc_sn:04d}"
            return psc_sn
        # psc_sn = input('\nEnter S/N')

    def _discover_psc_num(self) -> int | None:
        """
        Sweeps the network for active PSC units.
        Pings IP addresses 10.69.26.30 through .35 (PSC 1-6).

        Returns:
            int: The psc_num (1-6) if exactly one is found.
            None: If 0 are found, or if >1 are found.
            None will force _get_psc_pv_prefix to prompt user
        """
        # Map psc_num to its corresponding IP address
        psc_mapping = {
            1: "10.69.26.30",
            2: "10.69.26.31",
            3: "10.69.26.32",
            4: "10.69.26.33",
            5: "10.69.26.34",
            6: "10.69.26.35"
        }

        # Determine the operating system for correct ping flags
        sys_os = platform.system().lower()

        # Attempt up to 3 times
        for attempt in range(1, 4):
            print("Attempting to auto-detect PSCs")
            print(f"Network Sweep: Attempt {attempt} of 3...")
            successful_pscs = []

            # Ping the entire list once per attempt
            for psc_num, ip in psc_mapping.items():

                if sys_os == 'windows':
                    # -n 1 (send 1 packet), -w 500 (wait 500 milliseconds)
                    cmd = ['ping', '-n', '1', '-w', '500', ip]
                else:
                    # -c 1 (send 1 packet), -W 1 (wait 1 second)
                    cmd = ['ping', '-c', '1', '-W', '1', ip]

                try:
                    # Run silently by sending output to DEVNULL
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False
                    )

                    # A return code of 0 means the ping was successful
                    if result.returncode == 0:
                        successful_pscs.append(psc_num)

                except (subprocess.SubprocessError, OSError):
                    pass  # Treat any OS-level errors as a failed ping

            # Evaluate the results at the end of the pass
            if len(successful_pscs) > 1:
                print("Conflict: Multiple PSCs detected at IDs "
                      f"{successful_pscs}.\n\n Manual entry required.")
                return None

            elif len(successful_pscs) == 1:
                discovered_num = successful_pscs[0]
                print(f"[*] Success: Discovered PSC {discovered_num} at "
                      f"{psc_mapping[discovered_num]}")
                return discovered_num

            # If 0 were successful, the loop naturally continues
            # to the next attempt.

        # If the loop finishes all 3 attempts with 0 successes
        print("[!] Failed: No active PSCs could be reached on the network.")
        return None

    def _get_psc_pv_prefix(self) -> str:
        """Prompt for PSC #, to make PV Prefix, if auto-detection
        fails to discover the unit"""
        psc_num = None  # Initialize to None

        # Stays None if no ping/multiple units ping
        psc_num = self._discover_psc_num()

        # if Auto-Discovery fails, then prompt
        if psc_num is None:
            while True:
                psc_num = input("Enter the PSC Number under test "
                                "(e.g., for PSC 'lab{3}', enter "
                                "'3': ")

                # Check if numeric...
                if not psc_num.isdigit():
                    print("PSC Number must be a numeric, "
                          "between 1 and 6")
                    continue

                else:
                    # Check if between 1 and 6...
                    psc_num = int(psc_num)
                    if not 1 <= psc_num <= 6:
                        print("PSC number must be numeric, "
                              "between 1 and 6")
                        continue

                # psc_num is now confirmed to be valid...break
                break

        pv_prefix = f"lab{{{psc_num}}}"
        print(f"pv_prefix = {pv_prefix}")
        self.psc_num = psc_num
        return pv_prefix

    def init(self):
        """Initialize the PSC in the absence of the sequencer"""
        assert self.psc is not None

        for chan in range(1, self.num_channels + 1):
            self.psc.set_power_on1(chan, 0)
            self.psc.set_enable_on2(chan, 0)
            sleep(0.5)
            self.psc.set_power_on1(chan, 1)
            self.psc.set_enable_on2(chan, 1)

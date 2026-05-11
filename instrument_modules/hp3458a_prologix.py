import serial
from time import sleep

class HP3458A:
    """Class for interfacing the HP 3458A DMM via
    Prologix GPIB to USB Adapter"""
    def __init__(self,
                 port: str,
                 baud_rate: int = 115200,
                 timeout: int =30,
                 gpib_addr: int =24
                 ) -> None:

        self.ser = serial.Serial(port=port, baudrate=baud_rate, timeout=timeout)
        self.gpib_addr = gpib_addr

    def initialize(self) -> None:
        "Initialize DMM Settings via Prologix adapter"
        self.ser.write(f"++addr {self.gpib_addr}\n".encode('ascii'))
        self.ser.write(b"++auto 0\n")
        self.ser.write(b"AZERO ON\n")
        self.ser.write(b"NPLC 30\n")
        sleep(0.5)

    def set_range(self, dmm_range: float) -> None:
        """Set DMM Range, e.g. 1.0 or 0.1"""
        self.ser.write(f"RANGE {dmm_range}\n".encode('ascii'))

    def get_reading(self) -> float:
        """Triggers the measurement, returning a float"""
        self.ser.write(b"TARM SGL\n")
        sleep(1)
        self.ser.write(b"++auto 1\n")
        data = self.ser.read_until(b'\n', 1000)
        self.ser.write(b"++auto 0\n")
        return float(data.decode('ascii').strip())

    def close(self) -> None:
        """Close connection"""
        self.ser.close()

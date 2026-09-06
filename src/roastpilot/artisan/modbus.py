"""Minimal MODBUS TCP slave for Artisan integration.

Artisan acts as a MODBUS master (client); RoastPilot listens as a MODBUS TCP
slave (server). This module implements just enough of the MODBUS Application
Protocol (see modbus.org) for Artisan to read temperatures and write a burner
setpoint: Read Holding Registers (0x03), Write Single Register (0x06), and
Write Multiple Registers (0x10).

Default holding-register map (all 16-bit, configurable via ModbusContext):

  0  bean temperature (BT)        degC x 10   read
  1  exhaust temperature (ET)     degC x 10   read
  2  burner setpoint              % x 10      read/write
  3  burner actual                % x 10      read
  4  control mode (0=manual,1=auto)           read/write
  5  safety status (0=ok,1=fault)             read
"""

from __future__ import annotations

import socketserver
import struct
import threading


class ModbusError(Exception):
    """A MODBUS exception; `code` is the exception response code."""

    def __init__(self, code: int) -> None:
        super().__init__(f"MODBUS exception 0x{code:02x}")
        self.code = code


def _encode_temperature(value: float) -> int:
    return max(0, min(32767, round(value * 10.0)))


def _encode_percent(value: float) -> int:
    return max(0, min(1000, round(value * 10.0)))


class ModbusContext:
    """Holding-register store plus the default Artisan register map."""

    REGISTER_COUNT = 16
    BT_ADDR = 0
    ET_ADDR = 1
    BURNER_SETPOINT_ADDR = 2
    BURNER_ACTUAL_ADDR = 3
    CONTROL_MODE_ADDR = 4
    SAFETY_STATUS_ADDR = 5

    def __init__(self) -> None:
        self.registers: dict[int, int] = {i: 0 for i in range(self.REGISTER_COUNT)}

    # -- register access ----------------------------------------------------
    def read_holding(self, address: int, count: int) -> list[int]:
        self._check_address(address, count)
        return [self.registers.get(address + i, 0) for i in range(count)]

    def write_single(self, address: int, value: int) -> None:
        self._check_address(address, 1)
        self.registers[address] = value & 0xFFFF

    def write_multiple(self, address: int, values: list[int]) -> None:
        self._check_address(address, len(values))
        for i, value in enumerate(values):
            self.registers[address + i] = value & 0xFFFF

    def _check_address(self, address: int, count: int) -> None:
        if address < 0 or count < 1 or address + count > self.REGISTER_COUNT:
            raise ModbusError(0x02)  # illegal data address

    # -- typed convenience properties --------------------------------------
    @property
    def bean_temp_c(self) -> float:
        return self.registers[self.BT_ADDR] / 10.0

    @bean_temp_c.setter
    def bean_temp_c(self, value: float) -> None:
        self.registers[self.BT_ADDR] = _encode_temperature(value)

    @property
    def exhaust_temp_c(self) -> float:
        return self.registers[self.ET_ADDR] / 10.0

    @exhaust_temp_c.setter
    def exhaust_temp_c(self, value: float) -> None:
        self.registers[self.ET_ADDR] = _encode_temperature(value)

    @property
    def burner_setpoint_percent(self) -> float:
        return self.registers[self.BURNER_SETPOINT_ADDR] / 10.0

    @burner_setpoint_percent.setter
    def burner_setpoint_percent(self, value: float) -> None:
        self.registers[self.BURNER_SETPOINT_ADDR] = _encode_percent(value)

    @property
    def burner_actual_percent(self) -> float:
        return self.registers[self.BURNER_ACTUAL_ADDR] / 10.0

    @burner_actual_percent.setter
    def burner_actual_percent(self, value: float) -> None:
        self.registers[self.BURNER_ACTUAL_ADDR] = _encode_percent(value)

    @property
    def control_mode(self) -> int:
        return self.registers[self.CONTROL_MODE_ADDR]

    @control_mode.setter
    def control_mode(self, value: int) -> None:
        self.registers[self.CONTROL_MODE_ADDR] = int(value) & 0xFFFF

    @property
    def safety_fault(self) -> bool:
        return self.registers[self.SAFETY_STATUS_ADDR] != 0

    @safety_fault.setter
    def safety_fault(self, value: bool) -> None:
        self.registers[self.SAFETY_STATUS_ADDR] = 1 if value else 0


class _ModbusTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, context: ModbusContext) -> None:
        super().__init__(server_address, _ModbusHandler)
        self.context = context

    def process(self, pdu: bytes) -> bytes:
        if not pdu:
            return b""
        function = pdu[0]
        try:
            if function == 0x03:
                if len(pdu) != 5:
                    raise ModbusError(0x03)  # illegal data value
                address, quantity = struct.unpack(">HH", pdu[1:5])
                if not 1 <= quantity <= 125:
                    raise ModbusError(0x03)
                registers = self.context.read_holding(address, quantity)
                body = bytearray([0x03, quantity * 2])
                for register in registers:
                    body.extend(struct.pack(">H", register))
                return bytes(body)
            if function == 0x06:
                if len(pdu) != 5:
                    raise ModbusError(0x03)
                address, value = struct.unpack(">HH", pdu[1:5])
                self.context.write_single(address, value)
                return pdu
            if function == 0x10:
                if len(pdu) < 6:
                    raise ModbusError(0x03)
                address, quantity, byte_count = struct.unpack(">HHB", pdu[1:6])
                if byte_count != quantity * 2 or len(pdu) != 6 + byte_count:
                    raise ModbusError(0x03)
                if not 1 <= quantity <= 123:
                    raise ModbusError(0x03)
                values = [
                    struct.unpack(">H", pdu[6 + 2 * i : 8 + 2 * i])[0]
                    for i in range(quantity)
                ]
                self.context.write_multiple(address, values)
                return struct.pack(">BHH", 0x10, address, quantity)
            raise ModbusError(0x01)  # illegal function
        except ModbusError as error:
            return bytes([function | 0x80, error.code])


class _ModbusHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while True:
            header = self._recv_exact(7)
            if header is None:
                return
            transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
            if protocol_id != 0 or length < 2:
                return
            pdu = self._recv_exact(length - 1)
            if pdu is None:
                return
            response_pdu = self.server.process(pdu)
            response = (
                struct.pack(">HHHB", transaction_id, 0, len(response_pdu) + 1, unit_id)
                + response_pdu
            )
            self.request.sendall(response)

    def _recv_exact(self, size: int) -> bytes | None:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self.request.recv(size - len(chunks))
            if not chunk:
                return None
            chunks.extend(chunk)
        return bytes(chunks)


class ModbusServer:
    """A MODBUS TCP slave running on a background thread.

    Usage:
        context = ModbusContext()
        server = ModbusServer(context=context, host="0.0.0.0", port=1502)
        server.start()
        context.bean_temp_c = 201.3
        ...
        server.stop()
    """

    def __init__(
        self,
        context: ModbusContext | None = None,
        host: str = "127.0.0.1",
        port: int = 1502,
    ) -> None:
        self.context = context or ModbusContext()
        self.host = host
        self.port = port
        self._server = _ModbusTcpServer((host, port), self.context)
        self._thread: threading.Thread | None = None

    @property
    def bound_port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._server.shutdown()
        self._server.server_close()

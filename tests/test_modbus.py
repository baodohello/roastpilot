import socket
import struct
import unittest

from roastpilot.artisan.modbus import ModbusContext, ModbusServer


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("connection closed")
        data.extend(chunk)
    return bytes(data)


def _transact(port: int, pdu: bytes, unit: int = 1) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
        request = struct.pack(">HHHB", 1, 0, len(pdu) + 1, unit) + pdu
        sock.sendall(request)
        header = _recv_exact(sock, 7)
        _txid, _proto, length, _unit = struct.unpack(">HHHB", header)
        return _recv_exact(sock, length - 1)


class ModbusServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = ModbusContext()
        cls.server = ModbusServer(context=cls.context, host="127.0.0.1", port=0)
        cls.server.start()
        cls.port = cls.server.bound_port

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_read_holding_registers(self):
        self.context.bean_temp_c = 201.3
        self.context.exhaust_temp_c = 199.0
        response = _transact(self.port, struct.pack(">BHH", 0x03, 0, 2))
        self.assertEqual(response[0], 0x03)
        self.assertEqual(response[1], 4)  # byte count = 2 registers
        self.assertEqual(struct.unpack(">HH", response[2:6]), (2013, 1990))

    def test_write_single_register(self):
        pdu = struct.pack(">BHH", 0x06, ModbusContext.BURNER_SETPOINT_ADDR, 750)
        response = _transact(self.port, pdu)
        self.assertEqual(
            response, struct.pack(">BHH", 0x06, ModbusContext.BURNER_SETPOINT_ADDR, 750)
        )
        self.assertEqual(self.context.burner_setpoint_percent, 75.0)

    def test_write_multiple_registers(self):
        values = (500, 1)  # burner actual 50.0%, control mode = auto
        pdu = (
            struct.pack(">BHHB", 0x10, ModbusContext.BURNER_ACTUAL_ADDR, 2, 4)
            + struct.pack(">HH", *values)
        )
        response = _transact(self.port, pdu)
        self.assertEqual(
            response, struct.pack(">BHH", 0x10, ModbusContext.BURNER_ACTUAL_ADDR, 2)
        )
        self.assertEqual(self.context.burner_actual_percent, 50.0)
        self.assertEqual(self.context.control_mode, 1)

    def test_illegal_address_returns_exception(self):
        response = _transact(self.port, struct.pack(">BHH", 0x03, 100, 1))
        self.assertEqual(response, bytes([0x83, 0x02]))


if __name__ == "__main__":
    unittest.main()

import json
import time
import unittest

from websockets.sync.client import connect

from roastpilot.artisan.server import ArtisanWebSocketDevice


def _wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class ArtisanWebSocketDeviceTests(unittest.TestCase):
    def setUp(self):
        self.device = ArtisanWebSocketDevice(
            bt_provider=lambda: 201.3,
            et_provider=lambda: 199.0,
            host="127.0.0.1",
            port=0,
        )
        self.device.start()

    def tearDown(self):
        self.device.stop()

    def test_serves_bt_and_et_for_data_request(self):
        with connect(f"ws://127.0.0.1:{self.device.bound_port}/") as client:
            _wait_for(lambda: self.device.connection_count == 1)
            client.send(json.dumps({"command": "getData", "id": 44683, "machine": 0}))
            response = json.loads(client.recv(timeout=2))
        self.assertEqual(response, {"id": 44683, "data": {"BT": 201.3, "ET": 199.0}})

    def test_broadcast_pushes_messages_to_clients(self):
        with connect(f"ws://127.0.0.1:{self.device.bound_port}/") as client:
            _wait_for(lambda: self.device.connection_count == 1)
            self.device.broadcast({"Message": "CHARGE"})
            message = json.loads(client.recv(timeout=2))
        self.assertEqual(message, {"Message": "CHARGE"})

    def test_ignores_non_json_messages(self):
        with connect(f"ws://127.0.0.1:{self.device.bound_port}/") as client:
            _wait_for(lambda: self.device.connection_count == 1)
            client.send("not-json")
            client.send(json.dumps({"command": "getData", "id": 1}))
            response = json.loads(client.recv(timeout=2))
        self.assertEqual(response["data"], {"BT": 201.3, "ET": 199.0})


if __name__ == "__main__":
    unittest.main()

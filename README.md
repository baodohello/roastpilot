# RoastPilot

RoastPilot is a desktop profile studio for coffee roasting. It generates a
smooth, temperature-consistent target rate-of-rise (RoR) curve from Turning
Point, Dry End, First Crack, and Drop milestones, then lets you rehearse PID
tuning in a local simulator.

The current release is intentionally simulator-only: the application does not
connect to or command any roaster hardware.

## Run

Create an environment with Python 3.12, install the project, then run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
roastpilot
```

Use **Generate Target** after changing milestones. Enter the turning-point
(start) temperature and the three phase durations: Drying runs from the turning
point to Dry End, Maillard from Dry End to First Crack, and Development from
First Crack to Drop. RoastPilot fits a target BT curve through those milestones,
resamples it once per second, and derives the target RoR from that BT stream.
Select **Manual** to set a simulated burner level yourself, or **Auto** to have
the PID chase the RoR target. **Start Simulation** begins at the turning point
(0:00) and runs at 12× real time.

## Verify

```bash
python -m unittest discover -s tests
```

## Artisan integration (WebSocket device)

RoastPilot runs a WebSocket device server (`roastpilot.artisan.server.ArtisanWebSocketDevice`)
that Artisan attaches to as a device. In this exchange **Artisan is the client**:
configure the main device in Artisan as a WebSocket with endpoint
`ws://<host>:<port>/`, and Artisan polls RoastPilot each sampling interval.
RoastPilot answers with BT and ET in Artisan's documented JSON format:

```json
{"id": 44683, "data": {"BT": 189.2, "ET": 220.5}}
```

RoastPilot can also push CHARGE/DROP/event messages to Artisan via `broadcast()`.
See the [Artisan WebSocket docs](https://artisan-scope.org/devices/websockets/).
A MODBUS TCP device alternative is available in `roastpilot.artisan.modbus`.

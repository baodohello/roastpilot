# RoastPilot

RoastPilot is a desktop profile studio for coffee roasting. It generates a
smooth, temperature-consistent target rate-of-rise (RoR) curve from Charge,
Turning Point, Dry End, First Crack, and Drop milestones, then lets you rehearse PID tuning in a local
simulator.

The current release is intentionally simulator-only: the application does not
connect to or command any roaster hardware.

## Run

Create an environment with Python 3.12, install the project, then run:

```bash
pip install -e .
roastpilot
```

Use **Generate Target** after changing milestones. The phase inputs are
durations: Drying runs from Charge to Dry End, Maillard from Dry End to First
Crack, and Development from First Crack to Drop. High Charge BT values are
supported: set the expected Turning Point temperature and duration to create the
initial falling phase. During the simulation, RoastPilot also marks the actual
turning point when measured RoR crosses from negative to positive. Select **Manual** to set a
simulated burner level yourself, or **Auto** to have the PID chase the RoR
target. **Start Simulation** begins at Charge (0:00) and runs at
12× real time.

## Verify

```bash
python -m unittest discover -s tests
```

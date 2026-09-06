from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget

from roastpilot.core.bt_filter import RateOfRiseFilter
from roastpilot.core.pid import PIDController
from roastpilot.core.ror_engine import target_at
from roastpilot.core.roast_state import ControlMode, RoastState
from roastpilot.core.simulator import RoastSimulator
from roastpilot.core.target_ror import TargetRoR, generate_target_ror
from roastpilot.safety import BurnerGuard
from roastpilot.ui.control_panel import ControlPanelWidget
from roastpilot.ui.pid_panel import PidPanelWidget
from roastpilot.ui.roast_setup import RoastSetupWidget


class MainWindow(QMainWindow):
    """Safe local RoR simulator; it never writes to roaster hardware."""
    TICK_MS, SIM_SECONDS_PER_TICK = 250, 3.0

    def __init__(self) -> None:
        super().__init__()
        self.target: TargetRoR | None = None
        self.state, self.filter, self.pid = RoastState(), RateOfRiseFilter(), PIDController()
        self.simulator = RoastSimulator()
        self.guard = BurnerGuard(max_slew_per_s=50.0, stale_timeout_s=30.0)
        self.timer = QTimer(self); self.timer.timeout.connect(self.advance_simulation)
        self.setWindowTitle("RoastPilot — RoR Profile Studio"); self.resize(1250, 780)
        self.setup_ui(); self.generate_target()

    def setup_ui(self) -> None:
        central = QWidget(self); self.setCentralWidget(central); root = QVBoxLayout(central)
        header = QHBoxLayout(); title = QLabel("RoastPilot"); title.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.connection = QLabel("● SIMULATOR — NO HARDWARE OUTPUT"); self.connection.setStyleSheet("color: #3b7d3d; font-weight: bold;")
        self.auto_status = QLabel("MANUAL"); self.auto_status.setStyleSheet("font-weight: bold;")
        header.addWidget(title); header.addStretch(); header.addWidget(self.connection); header.addSpacing(20); header.addWidget(self.auto_status); root.addLayout(header)
        content = QHBoxLayout(); content.addWidget(self.create_controls(), 0); content.addWidget(self.create_graph(), 1); root.addLayout(content)

    def create_controls(self) -> QWidget:
        panel = QWidget(); panel.setMinimumWidth(335); layout = QVBoxLayout(panel)
        self.setup = RoastSetupWidget(); self.setup.generateRequested.connect(self.generate_target); layout.addWidget(self.setup)
        self.pid_panel = PidPanelWidget(); layout.addWidget(self.pid_panel)
        self.limits = ControlPanelWidget(); layout.addWidget(self.limits)
        burner = QGroupBox("SIMULATED BURNER"); burner_layout = QVBoxLayout(burner)
        self.output_label = QLabel("0.0 %"); self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.output_label.setStyleSheet("font-size: 30px; font-weight: bold;")
        self.manual_output = QSlider(Qt.Orientation.Horizontal); self.manual_output.setRange(0,100); self.manual_output.setValue(50); self.manual_output.valueChanged.connect(self.set_manual_output)
        burner_layout.addWidget(self.output_label); burner_layout.addWidget(self.manual_output); layout.addWidget(burner)
        modes = QHBoxLayout(); self.manual_button, self.auto_button = QPushButton("MANUAL"), QPushButton("AUTO")
        for item in (self.manual_button,self.auto_button): item.setCheckable(True)
        self.manual_button.setChecked(True); self.manual_button.clicked.connect(lambda: self.set_mode(ControlMode.MANUAL)); self.auto_button.clicked.connect(lambda: self.set_mode(ControlMode.AUTO))
        modes.addWidget(self.manual_button); modes.addWidget(self.auto_button); layout.addLayout(modes)
        self.run_button = QPushButton("START SIMULATION"); self.run_button.clicked.connect(self.toggle_simulation); self.reset_button = QPushButton("RESET"); self.reset_button.clicked.connect(self.reset_simulation)
        self.e_stop_button = QPushButton("E-STOP"); self.e_stop_button.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;"); self.e_stop_button.clicked.connect(self.emergency_stop)
        layout.addWidget(self.run_button); layout.addWidget(self.reset_button); layout.addWidget(self.e_stop_button); self.readout = QLabel("BT —   |   RoR —   |   Target —"); self.readout.setWordWrap(True); layout.addWidget(self.readout); layout.addStretch(); return panel

    def create_graph(self) -> QGroupBox:
        box = QGroupBox("ROAST PROFILE"); layout = QVBoxLayout(box); self.plot = pg.PlotWidget(); self.plot.setMaximumHeight(460); self.plot.setBackground(None); self.plot.setLabel("left","Bean temperature",units="°C"); self.plot.setLabel("right","RoR",units="°C/min"); self.plot.setLabel("bottom","Time",units="min"); self.plot.showGrid(x=True,y=True,alpha=.2); self.legend = self.plot.addLegend()
        self.ror_view = pg.ViewBox(); self.plot.showAxis("right"); self.plot.scene().addItem(self.ror_view); self.plot.getAxis("right").linkToView(self.ror_view); self.ror_view.setXLink(self.plot) # type: ignore
        def sync_ror_view():
            self.ror_view.setGeometry(self.plot.getViewBox().sceneBoundingRect())
            self.ror_view.linkedViewChanged(self.plot.getViewBox(), self.ror_view.XAxis)
        sync_ror_view(); self.plot.getViewBox().sigResized.connect(sync_ror_view)
        self.target_bt_curve = self.plot.plot(pen=pg.mkPen("#4aa3df",width=3),name="Target BT")
        self.actual_bt_curve = self.plot.plot(pen=pg.mkPen("#f39c12",width=2),name="Actual BT")
        self.target_curve = pg.PlotDataItem(pen=pg.mkPen("#8e44ad",width=3)); self.actual_curve = pg.PlotDataItem(pen=pg.mkPen("#c0392b",width=2))
        self.ror_view.addItem(self.target_curve); self.ror_view.addItem(self.actual_curve); self.legend.addItem(self.target_curve,"Target RoR"); self.legend.addItem(self.actual_curve,"Actual RoR")
        self.turn_marker, self.de_marker, self.fc_marker, self.drop_marker = pg.ScatterPlotItem(size=11,brush="#9b59b6"), pg.ScatterPlotItem(size=11,brush="#5cb85c"), pg.ScatterPlotItem(size=11,brush="#e67e22"), pg.ScatterPlotItem(size=11,brush="#d9534f")
        for marker in (self.turn_marker,self.de_marker,self.fc_marker,self.drop_marker): self.ror_view.addItem(marker)
        layout.addWidget(self.plot); self.summary = QLabel("Target RoR: —"); layout.addWidget(self.summary); return box

    @staticmethod
    def format_mmss(seconds: float) -> str:
        rounded = round(seconds)
        return f"{rounded // 60:02d}:{rounded % 60:02d}"

    def generate_target(self) -> None:
        try:
            start_temp, de_temp, dry, fc_temp, maillard, drop_temp, development = self.setup.milestone_inputs()
            de_time=dry; fc_time=de_time+maillard; drop_time=fc_time+development
            self.target=generate_target_ror(start_temp,de_time,de_temp,fc_time,fc_temp,drop_time,drop_temp, method=self.setup.bt_fit_method())
        except ValueError as error: QMessageBox.warning(self,"Invalid roast milestones",str(error)); return
        target=self.target; x,y=target.time_s/60,target.ror_c_per_min; start,de,fc,drop=target.milestones; de_index=int(abs(target.time_s-de.time_s).argmin()); fc_index=int(abs(target.time_s-fc.time_s).argmin())
        self.target_curve.setData(x,y); self.actual_curve.setData([],[]); self.target_bt_curve.setData(x,target.bt_c); self.actual_bt_curve.setData([],[])
        self.turn_marker.setData([start.time_s/60],[y[0]])
        self.de_marker.setData([de.time_s/60],[y[de_index]]); self.fc_marker.setData([fc.time_s/60],[y[fc_index]]); self.drop_marker.setData([drop.time_s/60],[y[-1]]); self.plot.setXRange(0,drop.time_s/60,padding=.05) # type: ignore
        total=drop.time_s
        self.summary.setText(f"Drying: {self.format_mmss(de.time_s)} ({de.time_s/total*100:.1f}%)   |   Maillard: {self.format_mmss(fc.time_s-de.time_s)} ({(fc.time_s-de.time_s)/total*100:.1f}%)   |   Development: {self.format_mmss(drop.time_s-fc.time_s)} ({(drop.time_s-fc.time_s)/total*100:.1f}%)   |   Drop: {self.format_mmss(drop.time_s)}"); self.reset_simulation()

    def set_mode(self, mode: ControlMode) -> None:
        self.state.mode=mode; self.pid.reset(); manual=mode is ControlMode.MANUAL; self.manual_button.setChecked(manual); self.auto_button.setChecked(not manual); self.auto_status.setText("MANUAL" if manual else "AUTO — SIMULATOR")
    def set_manual_output(self, value: int) -> None:
        if self.state.mode is ControlMode.AUTO: self.set_mode(ControlMode.MANUAL)
        self.state.burner_percent=self.guard.update(float(value), self.state.elapsed_s); self.update_readout()
    def toggle_simulation(self) -> None:
        if self.timer.isActive(): self.timer.stop(); self.state.running=False; self.run_button.setText("RESUME SIMULATION")
        elif self.target: self.timer.start(self.TICK_MS); self.state.running=True; self.run_button.setText("PAUSE SIMULATION")
    def reset_simulation(self) -> None:
        self.timer.stop(); self.pid.reset(); self.filter.reset(); self.simulator.reset(); self.guard.reset(); self.state.reset(self.setup.turn_temp.value())
        self.state.burner_percent=float(self.manual_output.value()); self.run_button.setText("START SIMULATION"); self.actual_curve.setData([],[]); self.actual_bt_curve.setData([],[]); self.update_readout()

    def emergency_stop(self) -> None:
        self.guard.emergency_stop(); self.timer.stop(); self.state.running=False; self.state.burner_percent=0.0; self.run_button.setText("START SIMULATION"); self.update_readout()

    def advance_simulation(self) -> None:
        if not self.target: return
        dt,time_s=self.SIM_SECONDS_PER_TICK,self.state.elapsed_s; desired=target_at(self.target,time_s); current=self.simulator.ror_c_per_min
        policy=self.limits.policy(); self.guard.max_slew_per_s=self.limits.rate_limit_percent_per_s()
        de_time_s,fc_time_s=self.target.milestones[1].time_s,self.target.milestones[2].time_s
        requested=self.state.burner_percent
        if self.state.mode is ControlMode.AUTO and desired is not None:
            kp,ki,kd=self.pid_panel.gains(); scale=policy.gain_scale(time_s,fc_time_s); self.pid.kp,self.pid.ki,self.pid.kd=kp*scale,ki*scale,kd*scale
            phase=policy.phase(time_s,de_time_s,fc_time_s); output=55+self.pid.update(desired,current,dt); requested=policy.clamp_to_envelope(output,phase)
        self.state.burner_percent=self.guard.update(requested,time_s)
        ror=self.simulator.step(self.state.burner_percent, self.state.bean_temp_c, dt)
        self.state.bean_temp_c+=ror*dt/60; self.state.elapsed_s+=dt; measured=self.filter.add(self.state.elapsed_s,self.state.bean_temp_c); self.state.ror_c_per_min=measured; self.state.target_ror_c_per_min=target_at(self.target,self.state.elapsed_s); self.state.history.append((self.state.elapsed_s,self.state.bean_temp_c,measured))
        self.actual_bt_curve.setData([row[0]/60 for row in self.state.history],[row[1] for row in self.state.history])
        actual = [row for row in self.state.history if row[2] is not None]
        self.actual_curve.setData([row[0]/60 for row in actual],[row[2] for row in actual])
        self.update_readout()
        if self.state.elapsed_s>=self.target.milestones[-1].time_s: self.timer.stop(); self.state.running=False; self.run_button.setText("SIMULATION COMPLETE"); QMessageBox.information(self,"Roast complete","The simulator reached the configured drop time. No hardware was controlled.")
    def update_readout(self) -> None:
        ror="—" if self.state.ror_c_per_min is None else f"{self.state.ror_c_per_min:.1f} °C/min"; target="—" if self.state.target_ror_c_per_min is None else f"{self.state.target_ror_c_per_min:.1f} °C/min"; start="—" if not self.target else f"{self.target.milestones[0].temp_c:.1f} °C"; self.output_label.setText(f"{self.state.burner_percent:.1f} %"); self.readout.setText(f"BT {self.state.bean_temp_c:.1f} °C   |   RoR {ror}\nTarget {target}   |   Start {start}\nElapsed {self.state.elapsed_s/60:.2f} min")

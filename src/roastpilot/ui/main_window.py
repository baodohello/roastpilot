from __future__ import annotations

from math import exp
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget

from roastpilot.core.bt_filter import RateOfRiseFilter
from roastpilot.core.pid import PIDController
from roastpilot.core.ror_engine import target_at
from roastpilot.core.roast_state import ControlMode, RoastState
from roastpilot.core.target_ror import TargetRoR, generate_target_ror, parse_mmss
from roastpilot.safety import clamp_output


class MainWindow(QMainWindow):
    """Safe local RoR simulator; it never writes to roaster hardware."""
    TICK_MS, SIM_SECONDS_PER_TICK = 250, 3.0

    def __init__(self) -> None:
        super().__init__()
        self.target: TargetRoR | None = None
        self.state, self.filter, self.pid = RoastState(), RateOfRiseFilter(), PIDController()
        self._previous_valid_ror: float | None = None
        self._sim_ror = 0.0
        self._timing_durations_s = [300.0, 210.0, 150.0]
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
        setup = QGroupBox("ROAST SETUP"); form = QFormLayout(setup)
        self.charge_temp = self.temp_spin(200)
        self.turn_temp, self.turn_time = self.temp_spin(90), QLineEdit("01:30")
        self.de_temp, self.de_time = self.temp_spin(150), QLineEdit()
        self.fc_temp, self.fc_time = self.temp_spin(196), QLineEdit()
        self.drop_temp, self.drop_time = self.temp_spin(210), QLineEdit()
        for label, control in (("Charge Temp",self.charge_temp),("Target Turn Temp",self.turn_temp),("Turn Duration",self.turn_time),("Dry End Temp",self.de_temp),("Drying Duration",self.de_time),("First Crack Temp",self.fc_temp),("Maillard Duration",self.fc_time),("Drop Temp",self.drop_temp),("Development Duration",self.drop_time)): form.addRow(label, control)
        self._connect_timing_inputs(); self._sync_timing_inputs()
        layout.addWidget(setup); button = QPushButton("GENERATE TARGET"); button.clicked.connect(self.generate_target); layout.addWidget(button)
        pid_box = QGroupBox("AUTO CONTROL"); pid_form = QFormLayout(pid_box)
        self.kp, self.ki, self.kd = self.pid_spin(3), self.pid_spin(.03), self.pid_spin(0)
        pid_form.addRow("Kp",self.kp); pid_form.addRow("Ki",self.ki); pid_form.addRow("Kd",self.kd); layout.addWidget(pid_box)
        burner = QGroupBox("SIMULATED BURNER"); burner_layout = QVBoxLayout(burner)
        self.output_label = QLabel("0.0 %"); self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.output_label.setStyleSheet("font-size: 30px; font-weight: bold;")
        self.manual_output = QSlider(Qt.Orientation.Horizontal); self.manual_output.setRange(0,100); self.manual_output.setValue(50); self.manual_output.valueChanged.connect(self.set_manual_output)
        burner_layout.addWidget(self.output_label); burner_layout.addWidget(self.manual_output); layout.addWidget(burner)
        modes = QHBoxLayout(); self.manual_button, self.auto_button = QPushButton("MANUAL"), QPushButton("AUTO")
        for item in (self.manual_button,self.auto_button): item.setCheckable(True)
        self.manual_button.setChecked(True); self.manual_button.clicked.connect(lambda: self.set_mode(ControlMode.MANUAL)); self.auto_button.clicked.connect(lambda: self.set_mode(ControlMode.AUTO))
        modes.addWidget(self.manual_button); modes.addWidget(self.auto_button); layout.addLayout(modes)
        self.run_button = QPushButton("START SIMULATION"); self.run_button.clicked.connect(self.toggle_simulation); self.reset_button = QPushButton("RESET"); self.reset_button.clicked.connect(self.reset_simulation)
        layout.addWidget(self.run_button); layout.addWidget(self.reset_button); self.readout = QLabel("BT —   |   RoR —   |   Target —"); self.readout.setWordWrap(True); layout.addWidget(self.readout); layout.addStretch(); return panel

    def create_graph(self) -> QGroupBox:
        box = QGroupBox("ROAST PROFILE"); layout = QVBoxLayout(box); self.plot = pg.PlotWidget(); self.plot.setMaximumHeight(460); self.plot.setBackground(None); self.plot.setLabel("left","Bean temperature",units="°C"); self.plot.setLabel("right","RoR",units="°C/min"); self.plot.setLabel("bottom","Time",units="min"); self.plot.showGrid(x=True,y=True,alpha=.2); self.legend = self.plot.addLegend()
        self.ror_view = pg.ViewBox(); self.plot.showAxis("right"); self.plot.scene().addItem(self.ror_view); self.plot.getAxis("right").linkToView(self.ror_view); self.ror_view.setXLink(self.plot)
        def sync_ror_view():
            self.ror_view.setGeometry(self.plot.getViewBox().sceneBoundingRect())
            self.ror_view.linkedViewChanged(self.plot.getViewBox(), self.ror_view.XAxis)
        sync_ror_view(); self.plot.getViewBox().sigResized.connect(sync_ror_view)
        self.target_bt_curve = self.plot.plot(pen=pg.mkPen("#4aa3df",width=3),name="Target BT")
        self.actual_bt_curve = self.plot.plot(pen=pg.mkPen("#f39c12",width=2),name="Actual BT")
        self.target_curve = pg.PlotDataItem(pen=pg.mkPen("#8e44ad",width=3)); self.actual_curve = pg.PlotDataItem(pen=pg.mkPen("#c0392b",width=2))
        self.ror_view.addItem(self.target_curve); self.ror_view.addItem(self.actual_curve); self.legend.addItem(self.target_curve,"Target RoR"); self.legend.addItem(self.actual_curve,"Actual RoR")
        self.charge_marker, self.turn_marker, self.actual_turn_marker, self.de_marker, self.fc_marker, self.drop_marker = pg.ScatterPlotItem(size=11,brush="#7f8c8d"), pg.ScatterPlotItem(size=11,brush="#9b59b6"), pg.ScatterPlotItem(size=14,brush="#e74c3c"), pg.ScatterPlotItem(size=11,brush="#5cb85c"), pg.ScatterPlotItem(size=11,brush="#e67e22"), pg.ScatterPlotItem(size=11,brush="#d9534f")
        for marker in (self.charge_marker,self.turn_marker,self.actual_turn_marker,self.de_marker,self.fc_marker,self.drop_marker): self.ror_view.addItem(marker)
        layout.addWidget(self.plot); self.summary = QLabel("Target RoR: —"); layout.addWidget(self.summary); return box

    @staticmethod
    def temp_spin(value: float) -> QDoubleSpinBox:
        spin=QDoubleSpinBox(); spin.setRange(50,300); spin.setDecimals(1); spin.setValue(value); spin.setSuffix(" °C"); return spin
    @staticmethod
    def pid_spin(value: float) -> QDoubleSpinBox:
        spin=QDoubleSpinBox(); spin.setRange(0,100); spin.setDecimals(3); spin.setValue(value); return spin

    @staticmethod
    def format_mmss(seconds: float) -> str:
        rounded = round(seconds)
        return f"{rounded // 60:02d}:{rounded % 60:02d}"

    def _connect_timing_inputs(self) -> None:
        duration_fields = (self.de_time, self.fc_time, self.drop_time)
        for index, field in enumerate(duration_fields): field.editingFinished.connect(lambda index=index, field=field: self._set_duration(index, field.text()))

    def _sync_timing_inputs(self) -> None:
        for field, duration in zip((self.de_time, self.fc_time, self.drop_time), self._timing_durations_s):
            field.setText(self.format_mmss(duration))

    def _timing_error(self, message: str) -> None:
        QMessageBox.warning(self, "Invalid phase timing", message); self._sync_timing_inputs()

    def _set_duration(self, index: int, value: str) -> None:
        try:
            duration = parse_mmss(value)
            if duration <= 0: raise ValueError("Duration must be greater than zero.")
        except ValueError as error:
            self._timing_error(str(error)); return
        self._timing_durations_s[index] = duration; self._sync_timing_inputs()


    def generate_target(self) -> None:
        try:
            turn_duration=parse_mmss(self.turn_time.text()); dry_duration,maillard_duration,development_duration=self._timing_durations_s
            if turn_duration >= dry_duration: raise ValueError("Turning-point duration must be shorter than the drying duration.")
            de_time=dry_duration; fc_time=de_time+maillard_duration; drop_time=fc_time+development_duration
            self.target=generate_target_ror(de_time,self.de_temp.value(),fc_time,self.fc_temp.value(),drop_time,self.drop_temp.value(),charge_temp_c=self.charge_temp.value(),turn_time_s=turn_duration,turn_temp_c=self.turn_temp.value())
        except ValueError as error: QMessageBox.warning(self,"Invalid roast milestones",str(error)); return
        target=self.target; x,y=target.time_s/60,target.ror_c_per_min; charge,turn,de,fc,drop=target.milestones; turn_index=int(abs(target.time_s-turn.time_s).argmin()); de_index=int(abs(target.time_s-de.time_s).argmin()); fc_index=int(abs(target.time_s-fc.time_s).argmin())
        visible = target.time_s >= target.ror_start_time_s
        self.target_curve.setData(x[visible],y[visible]); self.actual_curve.setData([],[]); self.target_bt_curve.setData(x,target.bt_c); self.actual_bt_curve.setData([],[]); self.actual_turn_marker.setData([],[]); self.charge_marker.setData([],[]); self.turn_marker.setData([turn.time_s/60],[y[turn_index]]); self.de_marker.setData([de.time_s/60],[y[de_index]]); self.fc_marker.setData([fc.time_s/60],[y[fc_index]]); self.drop_marker.setData([drop.time_s/60],[y[-1]]); self.plot.setXRange(0,drop.time_s/60,padding=.05)
        total=drop.time_s
        self.summary.setText(f"Drying: {self.format_mmss(de.time_s)} ({de.time_s/total*100:.1f}%)   |   Maillard: {self.format_mmss(fc.time_s-de.time_s)} ({(fc.time_s-de.time_s)/total*100:.1f}%)   |   Development: {self.format_mmss(drop.time_s-fc.time_s)} ({(drop.time_s-fc.time_s)/total*100:.1f}%)   |   Drop: {self.format_mmss(drop.time_s)}"); self.reset_simulation()

    def set_mode(self, mode: ControlMode) -> None:
        self.state.mode=mode; self.pid.reset(); manual=mode is ControlMode.MANUAL; self.manual_button.setChecked(manual); self.auto_button.setChecked(not manual); self.manual_output.setEnabled(manual); self.auto_status.setText("MANUAL" if manual else "AUTO — SIMULATOR")
    def set_manual_output(self, value: int) -> None:
        if self.state.mode is ControlMode.MANUAL: self.state.burner_percent=float(value); self.update_readout()
    def toggle_simulation(self) -> None:
        if self.timer.isActive(): self.timer.stop(); self.state.running=False; self.run_button.setText("RESUME SIMULATION")
        elif self.target: self.timer.start(self.TICK_MS); self.state.running=True; self.run_button.setText("PAUSE SIMULATION")
    def reset_simulation(self) -> None:
        self.timer.stop(); self.pid.reset(); self.filter.reset(); self._previous_valid_ror=None; self._sim_ror=0.0; self.state.reset(self.charge_temp.value())
        self.state.burner_percent=float(self.manual_output.value()); self.run_button.setText("START SIMULATION"); self.actual_curve.setData([],[]); self.actual_bt_curve.setData([],[]); self.update_readout()

    def advance_simulation(self) -> None:
        if not self.target: return
        dt,time_s=self.SIM_SECONDS_PER_TICK,self.state.elapsed_s; desired=target_at(self.target,time_s); current=self._sim_ror
        if self.state.mode is ControlMode.AUTO and desired is not None:
            self.pid.kp,self.pid.ki,self.pid.kd=self.kp.value(),self.ki.value(),self.kd.value(); self.state.burner_percent=clamp_output(55+self.pid.update(desired,current,dt))
        equilibrium=.54*self.state.burner_percent-.20*(self.state.bean_temp_c-25); ror=current+(equilibrium-current)*(1-exp(-dt/16)); self._sim_ror=ror
        self.state.bean_temp_c+=ror*dt/60; self.state.elapsed_s+=dt; measured=self.filter.add(self.state.elapsed_s,self.state.bean_temp_c); self.state.ror_c_per_min=measured; self.state.target_ror_c_per_min=target_at(self.target,self.state.elapsed_s); self.state.history.append((self.state.elapsed_s,self.state.bean_temp_c,measured))
        if measured is not None and self.state.turning_point_s is None and self._previous_valid_ror is not None and self._previous_valid_ror < 0 <= measured:
            self.state.turning_point_s,self.state.turning_point_temp_c=self.state.elapsed_s,self.state.bean_temp_c; self.actual_turn_marker.setData([self.state.elapsed_s/60],[measured])
        if measured is not None: self._previous_valid_ror=measured
        self.actual_bt_curve.setData([row[0]/60 for row in self.state.history],[row[1] for row in self.state.history])
        if self.state.turning_point_s is not None:
            actual = [row for row in self.state.history if row[0] >= self.state.turning_point_s and row[2] is not None]
            self.actual_curve.setData([row[0]/60 for row in actual],[row[2] for row in actual])
        self.update_readout()
        if self.state.elapsed_s>=self.target.milestones[-1].time_s: self.timer.stop(); self.state.running=False; self.run_button.setText("SIMULATION COMPLETE"); QMessageBox.information(self,"Roast complete","The simulator reached the configured drop time. No hardware was controlled.")
    def update_readout(self) -> None:
        ror="—" if self.state.ror_c_per_min is None else f"{self.state.ror_c_per_min:.1f} °C/min"; target="—" if self.state.target_ror_c_per_min is None else f"{self.state.target_ror_c_per_min:.1f} °C/min"; turning="Searching" if self.state.turning_point_s is None else f"{self.state.turning_point_temp_c:.1f} °C @ {self.state.turning_point_s/60:.2f} min"; self.output_label.setText(f"{self.state.burner_percent:.1f} %"); self.readout.setText(f"BT {self.state.bean_temp_c:.1f} °C   |   RoR {ror}\nTarget {target}   |   Turning Point {turning}\nElapsed {self.state.elapsed_s/60:.2f} min")

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from roastpilot.core.target_bt import BT_FIT_METHODS
from roastpilot.core.timeutil import parse_mmss


_BT_METHOD_LABELS = {
    "pchip": "PCHIP (monotone)",
    "cubic": "Cubic spline",
    "akima": "Akima",
    "linear": "Linear",
    "decline": "Declining RoR",
}


def _temp_spin(value: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(50, 300)
    spin.setDecimals(1)
    spin.setValue(value)
    spin.setSuffix(" °C")
    return spin


def _format_mmss(seconds: float) -> str:
    rounded = round(seconds)
    return f"{rounded // 60:02d}:{rounded % 60:02d}"


class RoastSetupWidget(QGroupBox):
    """Roast milestone inputs and the Generate Target action."""

    generateRequested = Signal()

    def __init__(self) -> None:
        super().__init__("ROAST SETUP")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.turn_temp = _temp_spin(80)
        self.de_temp, self.de_time = _temp_spin(150), QLineEdit()
        self.fc_temp, self.fc_time = _temp_spin(200), QLineEdit()
        self.drop_temp, self.drop_time = _temp_spin(215), QLineEdit()
        for label, control in (
            ("Turn Temp", self.turn_temp),
            ("Dry End Temp", self.de_temp),
            ("Drying Duration", self.de_time),
            ("First Crack Temp", self.fc_temp),
            ("Maillard Duration", self.fc_time),
            ("Drop Temp", self.drop_temp),
            ("Development Duration", self.drop_time),
        ):
            form.addRow(label, control)
        self.bt_method = QComboBox()
        for method in BT_FIT_METHODS:
            self.bt_method.addItem(_BT_METHOD_LABELS[method], method)
        form.addRow("BT Fit", self.bt_method)
        layout.addLayout(form)

        self._timing_durations_s = [180.0, 240.0, 120.0]
        duration_fields = (self.de_time, self.fc_time, self.drop_time)
        for index, field in enumerate(duration_fields):
            field.editingFinished.connect(
                lambda index=index, field=field: self._set_duration(index, field.text())
            )
        self._sync_timing_inputs()

        button = QPushButton("GENERATE TARGET")
        button.clicked.connect(self._request_generate)
        layout.addWidget(button)

    def milestone_inputs(self) -> tuple[float, float, float, float, float, float, float]:
        """Return (start temp, de temp, de time s, fc temp, fc time s, drop temp, drop time s)."""
        dry, maillard, development = self._timing_durations_s
        return (
            self.turn_temp.value(),
            self.de_temp.value(),
            dry,
            self.fc_temp.value(),
            maillard,
            self.drop_temp.value(),
            development,
        )

    def bt_fit_method(self) -> str:
        return self.bt_method.currentData()

    def _request_generate(self) -> None:
        self.generateRequested.emit()

    def _set_duration(self, index: int, value: str) -> None:
        try:
            duration = parse_mmss(value)
            if duration <= 0:
                raise ValueError("Duration must be greater than zero.")
        except ValueError as error:
            QMessageBox.warning(self, "Invalid phase timing", str(error))
            self._sync_timing_inputs()
            return
        self._timing_durations_s[index] = duration
        self._sync_timing_inputs()

    def _sync_timing_inputs(self) -> None:
        for field, duration in zip(
            (self.de_time, self.fc_time, self.drop_time), self._timing_durations_s
        ):
            field.setText(_format_mmss(duration))

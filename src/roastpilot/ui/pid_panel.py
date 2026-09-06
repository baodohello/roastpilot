from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox


def _pid_spin(value: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0, 100)
    spin.setDecimals(3)
    spin.setValue(value)
    return spin


class PidPanelWidget(QGroupBox):
    """PID gain inputs for the automatic RoR controller."""

    def __init__(self) -> None:
        super().__init__("AUTO CONTROL")
        form = QFormLayout(self)
        self.kp = _pid_spin(3)
        self.ki = _pid_spin(0.03)
        self.kd = _pid_spin(0)
        form.addRow("Kp", self.kp)
        form.addRow("Ki", self.ki)
        form.addRow("Kd", self.kd)

    def gains(self) -> tuple[float, float, float]:
        return self.kp.value(), self.ki.value(), self.kd.value()

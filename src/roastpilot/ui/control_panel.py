from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel

from roastpilot.core.control import ControlPolicy, GasEnvelope


def _spin(minimum: float, maximum: float, decimals: int, value: float, suffix: str = "") -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin


class ControlPanelWidget(QGroupBox):
    """Gas rate limit, per-phase min/max envelopes, and FC gain shaping."""

    def __init__(self) -> None:
        super().__init__("GAS LIMITS")
        form = QFormLayout(self)

        self.rate_limit = _spin(0.1, 100.0, 1, 10.0, " %/s")
        form.addRow("Rate limit", self.rate_limit)

        self.dry_min = _spin(0, 100, 0, 30, " %")
        self.dry_max = _spin(0, 100, 0, 100, " %")
        self.mai_min = _spin(0, 100, 0, 20, " %")
        self.mai_max = _spin(0, 100, 0, 90, " %")
        self.dev_min = _spin(0, 100, 0, 10, " %")
        self.dev_max = _spin(0, 100, 0, 80, " %")
        form.addRow("Drying", self._range(self.dry_min, self.dry_max))
        form.addRow("Maillard", self._range(self.mai_min, self.mai_max))
        form.addRow("Development", self._range(self.dev_min, self.dev_max))

        self.fc_scale = _spin(0.1, 1.0, 2, 0.5)
        self.fc_ramp = _spin(0, 120, 0, 30, " s")
        form.addRow("FC gain scale", self.fc_scale)
        form.addRow("FC ramp", self.fc_ramp)

    @staticmethod
    def _range(min_spin: QDoubleSpinBox, max_spin: QDoubleSpinBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(min_spin)
        row.addWidget(QLabel("–"))
        row.addWidget(max_spin)
        return row

    def rate_limit_percent_per_s(self) -> float:
        return self.rate_limit.value()

    def policy(self) -> ControlPolicy:
        return ControlPolicy(
            drying=GasEnvelope(self.dry_min.value(), self.dry_max.value()),
            maillard=GasEnvelope(self.mai_min.value(), self.mai_max.value()),
            development=GasEnvelope(self.dev_min.value(), self.dev_max.value()),
            fc_gain_scale=self.fc_scale.value(),
            fc_gain_ramp_s=self.fc_ramp.value(),
        )

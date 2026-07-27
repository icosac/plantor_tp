"""Composable Simple Temporal Network package."""

from .core import STNCore
from .optimization import STNOptimizationMixin
from .reports import STNReportsMixin
from .visualization import STNVisualizationMixin
from .utilities import SNAP_RE, STNUtilitiesMixin


class SimpleTemporalNetwork(STNReportsMixin, STNOptimizationMixin, STNVisualizationMixin, STNCore, STNUtilitiesMixin):
    """Simple Temporal Network with optimization, reporting, and visualization capabilities."""


__all__ = ["SimpleTemporalNetwork", "SNAP_RE"]

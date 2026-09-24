"""
Anomaly detection core used by the MCP server's `detect_anomalies` tool.

Two versions on purpose, kept side by side:

  v1_zscore  - the "naive first pass" (mean +/- 3*std).
               Problem: mean and std are themselves dragged around by the
               outliers you're trying to detect, and by trend/seasonality in
               the series. On a growing DAU curve or a weekend bump, this
               either misses real anomalies or flags normal weekly cycles.

  v2_robust  - the improved version. Two fixes:
               1. IQR-based thresholding (median/quartiles) instead of
                  mean/std, which is far less sensitive to the outliers
                  themselves.
               2. Detrending: instead of testing raw values, it tests each
                  point against a rolling median of its local window, so a
                  slow upward trend or weekly seasonality doesn't get
                  flagged as "anomalous".

This is the exact "before/after" the eval suite in evals/ measures.
"""
from __future__ import annotations
import statistics
from dataclasses import dataclass


@dataclass
class AnomalyResult:
    index: int
    value: float
    method: str
    reason: str


def v1_zscore(values: list[float], threshold: float = 3.0) -> list[AnomalyResult]:
    """Naive: flag anything more than `threshold` std-devs from the mean."""
    if len(values) < 2:
        return []
    mean = statistics.mean(values)
    std = statistics.pstdev(values)
    if std == 0:
        return []
    out = []
    for i, v in enumerate(values):
        z = (v - mean) / std
        if abs(z) > threshold:
            out.append(AnomalyResult(i, v, "v1_zscore", f"z={z:.2f}"))
    return out


def v2_robust(
    values: list[float],
    window: int = 14,
    iqr_multiplier: float = 1.8,
) -> list[AnomalyResult]:
    """
    Robust: compare each point to the rolling median of its local window
    (removes trend/seasonality), then flag using IQR (Tukey's fences),
    which stays stable even when the window itself contains an outlier.
    """
    n = len(values)
    if n < 3:
        return []

    out = []
    for i, v in enumerate(values):
        lo = max(0, i - window // 2)
        hi = min(n, i + window // 2 + 1)
        local = values[lo:hi]
        if len(local) < 4:
            continue

        sorted_local = sorted(local)
        q1 = sorted_local[len(sorted_local) // 4]
        q3 = sorted_local[(3 * len(sorted_local)) // 4]
        iqr = q3 - q1
        if iqr == 0:
            continue

        lower_fence = q1 - iqr_multiplier * iqr
        upper_fence = q3 + iqr_multiplier * iqr

        if v < lower_fence or v > upper_fence:
            out.append(
                AnomalyResult(
                    i, v, "v2_robust",
                    f"outside local IQR fence [{lower_fence:.2f}, {upper_fence:.2f}]"
                )
            )
    return out


METHODS = {
    "v1_zscore": v1_zscore,
    "v2_robust": v2_robust,
}

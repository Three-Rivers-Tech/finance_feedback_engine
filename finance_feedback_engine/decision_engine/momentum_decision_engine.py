"""Momentum decision engine shim.

THR-265 keeps the canonical implementation in
`finance_feedback_engine.optimization.momentum_signal` for optimization/backtesting
compatibility, while exposing the decision-engine path expected by sprint docs.
"""

from finance_feedback_engine.optimization.momentum_signal import MomentumDecisionEngine

__all__ = ["MomentumDecisionEngine"]

"""
Backward compatibility module for tracer.

This module now delegates to backend.app.context.tracer for actual implementation.
All imports of 'from backend.app import tracer' will continue to work.
"""
from backend.app.context.tracer import (
    new_run_id,
    set_run_id,
    get_run_id,
    emit,
    get_global_tracer,
)

__all__ = [
    "new_run_id",
    "set_run_id",
    "get_run_id",
    "emit",
    "get_global_tracer",
]

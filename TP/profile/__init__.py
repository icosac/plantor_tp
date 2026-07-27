"""Batch profiler implementation package."""

from .config import parse_args
from .main import main

__all__ = ["main", "parse_args"]

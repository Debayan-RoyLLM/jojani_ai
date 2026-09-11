"""Retrieval layer: find the reviews relevant to a query.

Public API: Retriever (with .search()). Everything else here is internal
building blocks (text helpers, models, corpus loading).
"""

from .retriever import Retriever

__all__ = ["Retriever"]

"""
Vectorization job package.

Contains the dedicated vectorization job that processes the vectorization queue
independently from ETL jobs.
"""

from .vectorization_job import run_vectorization_sync, VectorizationJobProcessor

__all__ = ['run_vectorization_sync', 'VectorizationJobProcessor']

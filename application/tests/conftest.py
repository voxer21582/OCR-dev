"""Shared synthetic-test isolation."""
import pytest

import alfa_document_intelligence.local_document_store as store_module


@pytest.fixture(autouse=True)
def _isolated_case_list_reference_cache():
    # Cached results are a pure function of authenticated bytes; clearing the
    # per-process cache only keeps call-count assertions independent.
    store_module._CASE_LIST_REFERENCE_CACHE.clear()
    yield
    store_module._CASE_LIST_REFERENCE_CACHE.clear()

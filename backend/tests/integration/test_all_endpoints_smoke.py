"""
Smoke tests for all API endpoints.

This test module validates that all API endpoints are reachable and return
the expected data structure shape, without making strict assumptions about
the contents (e.g., exact number of studies, users, etc.).

TESTING PHILOSOPHY:
-------------------
These tests follow a "no-fixture" approach because they aim to validate that
endpoints work correctly regardless of the current state of the test database.

Key principles:
1. No database setup fixtures - Tests run against the existing test database
  without requiring it to have specific test data.
2. Flexible response codes - Tests accept multiple valid HTTP status codes
  (e.g., 200, 404) depending on whether requested data exists or not.
3. Structure validation only - Tests validate that responses contain expected
  fields and have the correct type, but do not validate specific values or counts.
4. Graceful degradation - Tests verify that endpoints either return valid data
  or return properly formatted error responses.

This approach makes the tests:
- Less brittle - They won't break when test data changes
- Faster - No setup/teardown overhead
- More robust - They validate the API behavior regardless of database state

TEST COVERAGE:
--------------
The tests cover:
- Public endpoints (study config, ratings, active studies)
- Admin endpoints (dashboard, stats, exports)
- Authentication requirements
- Error handling (404, 403, etc.)
- Response structure validation
- Content-type validation (JSON, CSV, HTML)
"""

import pytest
import httpx
import os
from datetime import datetime, timezone, timedelta

from audiorating_backend.settings import settings


# Get the base URL from environment (default to CI Nginx port)
BASE_SCHEME = os.getenv("AR_BASE_SCHEME", "http://localhost:3000")
BASE_URL = f"{BASE_SCHEME}/" + settings.rootpath.strip("/")


# ============================================================================
# Smoke Tests for Endpoints
# ============================================================================

@pytest.mark.asyncio
async def test_root_api_endpoint_reachable():
    """
    Test that the root /api endpoint is reachable and returns the expected response shape.
    """
    url = f"{BASE_URL}/api"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "message" in data


@pytest.mark.asyncio
async def test_active_open_studies_endpoint_structure():
    """
    Test that /api/active_open_study_names returns a list with expected item structure.
    """
    url = f"{BASE_URL}/api/active_open_study_names"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    # Validate structure of each item (if any exist)
    for item in data:
        assert isinstance(item, dict)
        assert "name_short" in item
        assert "name" in item
        assert "description" in item


@pytest.mark.asyncio
async def test_study_config_endpoint_structure_with_valid_study():
    """
    Test that /api/participants/{participant_id}/studies/{study_name}/config
    returns expected configuration structure for a valid study.
    
    Uses 'default' study name which is typically available in test setups.
    """
    # Use the 'default' study which is commonly available
    url = f"{BASE_URL}/api/participants/test_user_smoke_test/studies/default/config"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    # Accept either 200 (study exists) or 403 (not authorized) or 404 (study doesn't exist)
    # We just want to verify the endpoint responds and returns JSON
    assert response.status_code in [200, 403, 404, 403]
    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_ratings_endpoint_structure():
    """
    Test that GET /api/participants/{participant_id}/studies/{study}/songs/{song_index}/ratings
    returns expected ratings structure.
    """
    # Use the 'default' study which is commonly available
    url = f"{BASE_URL}/api/participants/test_user_smoke_test/studies/default/songs/0/ratings"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    # Accept either 200 or 404 depending on whether study/song exists
    assert response.status_code in [200, 404, 403]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)
        assert "participant_id" in data
        assert "study_name_short" in data
        assert "song_index" in data
        assert "ratings" in data


@pytest.mark.asyncio
async def test_admin_stats_endpoint_structure():
    """
    Test that /admin/api/stats returns expected admin statistics structure.
    Requires authentication.
    """
    url = f"{BASE_URL}/admin/api/stats"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=(settings.admin_username, settings.admin_password)
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

    # Validate top-level fields
    assert "studies" in data
    assert "total_studies" in data
    assert "timestamp" in data
    assert isinstance(data["studies"], list)


@pytest.mark.asyncio
async def test_admin_runtime_export_endpoint_structure():
    """
    Test that /api/admin/export/studies-runtime-config returns expected export structure.
    Requires authentication.
    """
    url = f"{BASE_URL}/api/admin/export/studies-runtime-config"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=(settings.admin_username, settings.admin_password)
        )

    assert response.status_code == 200

    # Check Content-Disposition header for file download
    assert "attachment; filename=" in response.headers.get("Content-Disposition", "")

    data = response.json()
    assert isinstance(data, dict)

    # Validate top-level fields
    assert "studies_config" in data
    assert "logged_ratings" in data
    assert "audiorating_backend_version" in data


@pytest.mark.asyncio
async def test_admin_runtime_export_per_study_endpoint_structure():
    """
    Test that /api/admin/export/studies-runtime-config?study_name=... 
    returns expected export structure for a single study (if it exists).
    Requires authentication.
    """
    # Try with 'default' study which is commonly available
    url = f"{BASE_URL}/api/admin/export/studies-runtime-config?study_name=default"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=(settings.admin_username, settings.admin_password)
        )

    # Should either return 200 or 404 if study doesn't exist
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)
        assert "studies_config" in data
        assert "logged_ratings" in data


@pytest.mark.asyncio
async def test_admin_participants_endpoint_structure():
    """
    Test that /api/admin/studies/{study_name}/participants returns participant list structure.
    Requires authentication.
    """
    # Try with 'default' study which is commonly available
    url = f"{BASE_URL}/api/admin/studies/default/participants"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=(settings.admin_username, settings.admin_password)
        )

    # Should either return 200 or 404 if study doesn't exist
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_admin_dashboard_endpoint_returns_html():
    """
    Test that /admin page returns HTML content.
    Requires authentication.
    """
    url = f"{BASE_URL}/admin"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=(settings.admin_username, settings.admin_password)
        )

    assert response.status_code == 200
    content_type = response.headers.get("Content-Type", "")
    assert "text/html" in content_type


@pytest.mark.asyncio
async def test_admin_participant_management_endpoint_returns_html():
    """
    Test that /admin/participant-management page returns HTML content.
    Requires authentication.
    """
    url = f"{BASE_URL}/admin/participant-management"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=(settings.admin_username, settings.admin_password)
        )

    assert response.status_code == 200
    content_type = response.headers.get("Content-Type", "")
    assert "text/html" in content_type


# ============================================================================
# Tests for Authorization and Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_admin_endpoint_requires_authentication():
    """
    Test that admin endpoints return 401 when accessed without authentication.
    """
    url = f"{BASE_URL}/admin"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_export_endpoint_requires_authentication():
    """
    Test that admin export endpoint returns 401 when accessed without authentication.
    """
    url = f"{BASE_URL}/api/admin/export/studies-runtime-config"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_study_config_unknown_study_returns_404():
    """
    Test that requesting config for non-existent study returns 404.
    """
    url = f"{BASE_URL}/api/participants/test_user/studies/__nonexistent_study__/config"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data

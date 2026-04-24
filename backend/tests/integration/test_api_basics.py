import pytest
import httpx
import os
from datetime import datetime, timedelta, timezone

# import settings.py to get BASE_URL from environment variables
from audiorating_backend.settings import settings


# Get the base URL from environment (default to CI Nginx port)
# In your CI, you will set BASE_URL=http://localhost:3000/ar_backend
BASE_SCHEME = os.getenv("AR_BASE_SCHEME", "http://localhost:3000")
BASE_URL = f"{BASE_SCHEME}/" + settings.rootpath.strip(
    "/"
)  # Ensure no leading or trailing slash


@pytest.mark.asyncio
async def test_api_is_reachable_through_proxy_with_basepath():
    """
    Test the root /api endpoint via the reverse proxy to verify
    root_path configuration and Nginx routing.
    """
    # Construct the full URL
    url = f"{BASE_URL}/api"
    # print(f"Trying to reach backend at: {url} (rootpath is set to: '{settings.rootpath}')")

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "is running" in data["message"]
    # print(f"Successfully reached proxy at: {url} (rootpath is set to: '{settings.rootpath}')")


@pytest.mark.asyncio
async def test_admin_interface_reachable_through_proxy_with_auth():
    """
    Test the protected /admin page via the reverse proxy
    using HTTP Basic Authentication.
    """
    # Construct the URL
    url = f"{BASE_URL}/admin"

    async with httpx.AsyncClient() as client:
        # Pass the auth tuple: (username, password)
        response = await client.get(
            url, auth=(settings.admin_username, settings.admin_password)
        )

    # Assertions
    # We expect 200 for a successful authenticated request
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # We expect to receive HTML page content for the admin interface
    assert "text/html" in response.headers.get(
        "Content-Type", ""
    ), "Expected HTML content"


@pytest.mark.asyncio
async def test_admin_interface_not_reachable_without_auth():
    """
    Test the protected /admin page via the reverse proxy
    without HTTP Basic Authentication. Should get a 401 Unauthorized response.
    """
    # Construct the URL
    url = f"{BASE_URL}/admin"

    async with httpx.AsyncClient() as client:
        # Do not pass any authentication
        response = await client.get(url)  # no auth

    # Assertions
    # We expect 401 for an unauthorized request
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"


@pytest.mark.asyncio
async def test_admin_interface_not_reachable_with_incorrect_auth():
    """
    Test the protected /admin page via the reverse proxy
    with incorrect HTTP Basic Authentication. Should get a 401 Unauthorized response.
    """
    # Construct the URL
    url = f"{BASE_URL}/admin"

    async with httpx.AsyncClient() as client:
        # Pass incorrect authentication
        response = await client.get(url, auth=("wrong_user", "wrong_pass"))

    # Assertions
    # We expect 401 for an unauthorized request
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"


@pytest.mark.asyncio
async def test_active_open_studies_endpoint_returns_list_shape():
    """Smoke-test active study endpoint and validate list item shape."""
    url = f"{BASE_URL}/api/active_open_study_names"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    for item in data:
        assert isinstance(item, dict)
        assert "name_short" in item
        assert "name" in item
        assert "description" in item


@pytest.mark.asyncio
async def test_admin_stats_endpoint_returns_expected_top_level_fields():
    """Smoke-test authenticated admin stats endpoint and response format."""
    url = f"{BASE_URL}/admin/api/stats"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url, auth=(settings.admin_username, settings.admin_password)
        )

    assert response.status_code == 200
    data = response.json()
    assert "studies" in data
    assert "total_studies" in data
    assert "timestamp" in data
    assert isinstance(data["studies"], list)


@pytest.mark.asyncio
async def test_study_config_unknown_study_returns_not_found_json():
    """Ensure study config endpoint is reachable and returns JSON error shape for unknown study."""
    participant_id = "integration_test_user"
    unknown_study_name = "__unknown_study_for_integration_test__"
    url = f"{BASE_URL}/api/participants/{participant_id}/studies/{unknown_study_name}/config"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in str(data["detail"]).lower()


@pytest.mark.asyncio
async def test_admin_runtime_studies_export_returns_expected_top_level_shape():
    """Smoke-test authenticated runtime studies export endpoint and response shape."""
    url = f"{BASE_URL}/api/admin/export/studies-runtime-config"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url, auth=(settings.admin_username, settings.admin_password)
        )

    assert response.status_code == 200
    assert "attachment; filename=" in response.headers.get("Content-Disposition", "")

    data = response.json()
    assert "studies_config" in data
    assert "logged_ratings" in data
    assert "audiorating_backend_version" in data
    assert isinstance(data["studies_config"], dict)
    assert isinstance(data["studies_config"].get("studies"), list)
    assert isinstance(data["logged_ratings"], dict)

    if data["studies_config"]["studies"]:
        first_study = data["studies_config"]["studies"][0]
        assert "name" in first_study
        assert "name_short" in first_study
        assert "songs_to_rate" in first_study
        assert "rating_dimensions" in first_study
        assert "study_participant_ids" in first_study
        assert "allow_unlisted_participants" in first_study

        assert first_study["name_short"] in data["logged_ratings"]


@pytest.mark.asyncio
async def test_admin_can_update_study_collection_window_and_restore():
    """Integration test for updating study collection window through admin API."""
    stats_url = f"{BASE_URL}/admin/api/stats"

    async with httpx.AsyncClient() as client:
        stats_response = await client.get(
            stats_url, auth=(settings.admin_username, settings.admin_password)
        )
        assert stats_response.status_code == 200
        stats_data = stats_response.json()

        studies = stats_data.get("studies", [])
        if not studies:
            pytest.skip("No studies available to test collection-window update")

        study = studies[0]
        study_name_short = study["name_short"]
        original_start = study["data_collection_start"]
        original_end = study["data_collection_end"]

        parsed_end = datetime.fromisoformat(original_end.replace("Z", "+00:00"))
        new_end = (parsed_end + timedelta(days=1)).astimezone(timezone.utc)
        new_end_iso = new_end.isoformat().replace("+00:00", "Z")

        update_url = (
            f"{BASE_URL}/api/admin/studies/{study_name_short}/collection-window"
        )

        try:
            update_response = await client.patch(
                update_url,
                auth=(settings.admin_username, settings.admin_password),
                json={"data_collection_end": new_end_iso},
            )

            assert update_response.status_code == 200, update_response.text
            payload = update_response.json()
            assert payload["study_name_short"] == study_name_short
            updated_end = datetime.fromisoformat(
                payload["updated"]["data_collection_end"].replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            expected_end = datetime.fromisoformat(
                new_end_iso.replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            assert updated_end == expected_end
        finally:
            await client.patch(
                update_url,
                auth=(settings.admin_username, settings.admin_password),
                json={
                    "data_collection_start": original_start,
                    "data_collection_end": original_end,
                },
            )

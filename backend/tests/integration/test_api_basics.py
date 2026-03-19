import pytest
import httpx
import os

# import settings.py to get BASE_URL from environment variables
from audiorating_backend.settings import settings


# Get the base URL from environment (default to CI Nginx port)
# In your CI, you will set BASE_URL=http://localhost:3000/ar_backend
BASE_SCHEME = os.getenv("AR_BASE_SCHEME", "http://localhost:3000")
BASE_URL = f"{BASE_SCHEME}/" + settings.rootpath.strip("/")  # Ensure no leading or trailing slash


@pytest.mark.asyncio
async def test_api_is_reachable_through_proxy_with_basepath():
    """
    Test the root /api endpoint via the reverse proxy to verify
    root_path configuration and Nginx routing.
    """
    # Construct the full URL
    url = f"{BASE_URL}/api"
    #print(f"Trying to reach backend at: {url} (rootpath is set to: '{settings.rootpath}')")

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "is running" in data["message"]
    #print(f"Successfully reached proxy at: {url} (rootpath is set to: '{settings.rootpath}')")


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
        response = await client.get(url, auth=(settings.admin_username, settings.admin_password))

    # Assertions
    # We expect 200 for a successful authenticated request
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # We expect to receive HTML page content for the admin interface
    assert "text/html" in response.headers.get("Content-Type", ""), "Expected HTML content"


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

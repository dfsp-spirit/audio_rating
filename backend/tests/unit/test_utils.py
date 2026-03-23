from datetime import timezone

from audiorating_backend.utils import utc_now


def test_utc_now_is_timezone_aware_utc():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc

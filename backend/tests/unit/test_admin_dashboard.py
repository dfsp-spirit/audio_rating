import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from starlette.requests import Request

os.environ.setdefault("AR_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AR_ALLOWED_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("AR_API_ADMIN_USERNAME", "test_admin")
os.environ.setdefault("AR_API_ADMIN_PASSWORD", "test_password")

from audiorating_backend import api as api_module


class FakeExecResult:
    def __init__(self, data):
        self._data = data

    def all(self):
        return self._data

    def first(self):
        if isinstance(self._data, list):
            return self._data[0] if self._data else None
        return self._data


class FakeSession:
    def __init__(self, results):
        self._results = list(results)

    def exec(self, _statement):
        if not self._results:
            raise AssertionError("Unexpected extra session.exec() call")
        return FakeExecResult(self._results.pop(0))


@pytest.mark.asyncio
async def test_admin_dashboard_handles_legacy_localized_dict_fields(monkeypatch):
    now = datetime.now(timezone.utc)

    study = SimpleNamespace(
        id="study-1",
        name_short="legacy_study",
        name="Legacy Study",
        description="Legacy description",
        allow_unlisted_participants=False,
        data_collection_start=now - timedelta(days=1),
        data_collection_end=now + timedelta(days=1),
        created_at=now - timedelta(days=2),
    )
    song_link = SimpleNamespace(song_id="song-1")
    participant_link = SimpleNamespace(participant_id="participant-1")
    participant = SimpleNamespace(id="participant-1", created_at=now - timedelta(hours=2))
    rating = SimpleNamespace(
        rating_name="valence",
        timestamp=now - timedelta(hours=1),
        created_at=now - timedelta(hours=2),
    )
    song = SimpleNamespace(
        display_name={"en": "Improvisation 1", "de": "Improvisation 1 DE"},
        media_url="audio_files/legacy/song.mp3",
    )
    dimension = SimpleNamespace(
        dimension_title="flow",
        num_values=5,
        minimal_value=1,
        default_value=3,
        description={"en": "Flow description", "de": "Flow Beschreibung"},
    )

    fake_session = FakeSession(
        [
            [study],
            [song_link],
            [participant_link],
            [participant.id],
            [(rating, participant, song, 2)],
            [dimension],
        ]
    )

    captured = {}

    def fake_template_response(template_name, context):
        captured["template_name"] = template_name
        captured["context"] = context
        return SimpleNamespace(template_name=template_name, context=context)

    monkeypatch.setattr(api_module.templates, "TemplateResponse", fake_template_response)

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/admin",
            "raw_path": b"/admin",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "root_path": "/ar_backend",
            "app": api_module.app,
        }
    )

    response = await api_module.admin_dashboard(
        request=request,
        session=fake_session,
        current_admin="test_admin",
    )

    assert response.template_name == "admin_dashboard.html"
    assert captured["context"]["api_base"] == "http://testserver/ar_backend"

    studies = captured["context"]["studies"]
    assert len(studies) == 1

    active_participant = studies[0]["active_participants"][0]
    assert active_participant["songs_rated"] == ["Improvisation 1"]
    assert active_participant["ratings"][0]["song"] == "Improvisation 1"

    rating_dimensions = studies[0]["rating_dimensions"]
    assert rating_dimensions[0]["description"] == "Flow description"

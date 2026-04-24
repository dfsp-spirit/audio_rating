import json

from audiorating_backend.frontend_audio_check import check_frontend_audio_files


def _config_payload(media_url: str):
    return {
        "studies": [
            {
                "name": "Test Study",
                "name_short": "test_study",
                "songs_to_rate": [{"media_url": media_url, "display_name": "Song A"}],
                "rating_dimensions": [{"dimension_title": "valence", "num_values": 7}],
                "data_collection_start": "2024-01-01T00:00:00Z",
                "data_collection_end": "2030-01-01T00:00:00Z",
            }
        ]
    }


def test_check_frontend_audio_files_returns_true_when_all_files_exist(tmp_path):
    frontend_dir = tmp_path / "frontend"
    audio_file = frontend_dir / "audio_files" / "default" / "song_a.wav"
    audio_file.parent.mkdir(parents=True)
    audio_file.write_text("dummy", encoding="utf-8")

    config_file = tmp_path / "studies.json"
    config_file.write_text(
        json.dumps(_config_payload("audio_files/default/song_a.wav")),
        encoding="utf-8",
    )

    assert check_frontend_audio_files(str(frontend_dir), str(config_file)) is True


def test_check_frontend_audio_files_returns_false_when_file_missing(tmp_path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()

    config_file = tmp_path / "studies.json"
    config_file.write_text(
        json.dumps(_config_payload("audio_files/default/missing.wav")),
        encoding="utf-8",
    )

    assert check_frontend_audio_files(str(frontend_dir), str(config_file)) is False


def test_check_frontend_audio_files_returns_false_when_config_missing(tmp_path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()

    assert (
        check_frontend_audio_files(str(frontend_dir), str(tmp_path / "missing.json"))
        is False
    )

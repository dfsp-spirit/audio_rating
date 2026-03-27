import json
from pathlib import Path

import pytest

from audiorating_backend.parsers.studies_config import (
    CfgFileRatingDimension,
    CfgFileSong,
    load_studies_config,
)


def _minimal_studies_payload(song_url: str = "audio_files/default/song.wav"):
    return {
        "studies": [
            {
                "name": "Test Study",
                "name_short": "test_study",
                "songs_to_rate": [{"media_url": song_url, "display_name": "Song"}],
                "rating_dimensions": [{"dimension_title": "valence", "num_values": 7}],
                "data_collection_start": "2024-01-01T00:00:00Z",
                "data_collection_end": "2030-01-01T00:00:00Z",
            }
        ]
    }


def test_cfg_file_song_fills_missing_description():
    song = CfgFileSong(media_url="foo/bar/song_a.wav", display_name="")
    assert song.display_name == "song_a"
    assert song.description == "song_a"


def test_rating_dimension_defaults_are_filled():
    dim = CfgFileRatingDimension(dimension_title="valence", num_values=7)
    assert dim.minimal_value == 1
    assert dim.default_value == 3


def test_rating_dimension_default_value_must_be_in_range():
    with pytest.raises(ValueError, match="default_value"):
        CfgFileRatingDimension(
            dimension_title="arousal",
            num_values=5,
            minimal_value=1,
            default_value=99,
        )


def test_load_studies_config_from_json(tmp_path):
    config_file = tmp_path / "studies.json"
    config_file.write_text(json.dumps(_minimal_studies_payload()), encoding="utf-8")

    cfg = load_studies_config(str(config_file))
    assert len(cfg.studies) == 1
    assert cfg.studies[0].name_short == "test_study"


def test_load_studies_config_with_multilingual_fields(tmp_path):
    payload = {
        "studies": [
            {
                "name": "Test Study",
                "name_short": "test_study",
                "default_language": "de",
                "description": {"en": "English desc", "de": "Deutsche Beschreibung"},
                "custom_text_instructions": {"en": "Instructions", "de": "Anleitung"},
                "custom_text_thank_you": {"en": "Thanks", "de": "Danke"},
                "songs_to_rate": [
                    {
                        "media_url": "audio_files/default/song.wav",
                        "display_name": {"en": "Song", "de": "Lied"},
                        "description": {"en": "Desc", "de": "Beschreibung"}
                    }
                ],
                "rating_dimensions": [
                    {
                        "dimension_title": "valence",
                        "display_name": {"en": "Valence", "de": "Valenz"},
                        "num_values": 7,
                        "description": {"en": "Desc", "de": "Beschreibung"}
                    }
                ],
                "data_collection_start": "2024-01-01T00:00:00Z",
                "data_collection_end": "2030-01-01T00:00:00Z"
            }
        ]
    }

    config_file = tmp_path / "studies_multilingual.json"
    config_file.write_text(json.dumps(payload), encoding="utf-8")

    cfg = load_studies_config(str(config_file))

    assert cfg.studies[0].default_language == "de"
    assert isinstance(cfg.studies[0].description, dict)
    assert cfg.studies[0].songs_to_rate[0].display_name["de"] == "Lied"
    assert cfg.studies[0].rating_dimensions[0].display_name["en"] == "Valence"


def test_load_studies_config_unsupported_suffix_raises(tmp_path):
    config_file = tmp_path / "studies.txt"
    config_file.write_text("not used", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported config file format"):
        load_studies_config(str(config_file))


def test_load_studies_config_missing_file_raises(tmp_path):
    missing_file = Path(tmp_path / "does_not_exist.json")

    with pytest.raises(FileNotFoundError, match="Studies configuration file not found"):
        load_studies_config(str(missing_file))

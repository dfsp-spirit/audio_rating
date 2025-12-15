# tests/test_study_config.py
import pytest
from datetime import datetime, timezone
from audiorating_backend.parsers.studies_config import CfgFileStudyConfig


class TestStudyConfigValidations:
    """Concise test suite for CfgFileStudyConfig validations"""

    @pytest.fixture
    def base_config(self):
        """Base valid configuration"""
        return {
            "name": "Test Study",
            "name_short": "test_study",
            "songs_to_rate": [
                {"media_url": "song1.wav", "display_name": "Song 1"}
            ],
            "rating_dimensions": [
                {"dimension_title": "valence", "num_values": 8}
            ],
            "data_collection_start": "2024-01-01T00:00:00Z",
            "data_collection_end": "2024-12-31T23:59:59Z"
        }

    def test_valid_config(self, base_config):
        """Test that valid config passes all validations"""
        config = CfgFileStudyConfig(**base_config)
        assert config.name == "Test Study"
        assert isinstance(config.data_collection_start, datetime)
        assert config.data_collection_start.tzinfo == timezone.utc

    def test_empty_songs_to_rate(self, base_config):
        """Test that empty songs_to_rate list is rejected"""
        base_config["songs_to_rate"] = []
        with pytest.raises(ValueError, match="cannot be empty"):
            CfgFileStudyConfig(**base_config)

    def test_empty_rating_dimensions(self, base_config):
        """Test that empty rating_dimensions list is rejected"""
        base_config["rating_dimensions"] = []
        with pytest.raises(ValueError, match="cannot be empty"):
            CfgFileStudyConfig(**base_config)

    def test_duplicate_song_media_urls(self, base_config):
        """Test duplicate media_url in songs_to_rate"""
        base_config["songs_to_rate"] = [
            {"media_url": "same.wav", "display_name": "Song 1"},
            {"media_url": "same.wav", "display_name": "Song 2"}
        ]
        with pytest.raises(ValueError, match="Duplicate media_url"):
            CfgFileStudyConfig(**base_config)

    def test_duplicate_song_display_names(self, base_config):
        """Test duplicate display_name in songs_to_rate"""
        base_config["songs_to_rate"] = [
            {"media_url": "song1.wav", "display_name": "Same Name"},
            {"media_url": "song2.wav", "display_name": "Same Name"}
        ]
        with pytest.raises(ValueError, match="Duplicate display_name"):
            CfgFileStudyConfig(**base_config)

    def test_duplicate_dimension_titles(self, base_config):
        """Test duplicate dimension_title in rating_dimensions"""
        base_config["rating_dimensions"] = [
            {"dimension_title": "valence", "num_values": 8},
            {"dimension_title": "valence", "num_values": 5}
        ]
        with pytest.raises(ValueError, match="Duplicate dimension_title"):
            CfgFileStudyConfig(**base_config)

    def test_duplicate_participant_ids(self, base_config):
        """Test duplicate entries in study_participant_ids"""
        base_config["study_participant_ids"] = ["user1", "user1"]
        with pytest.raises(ValueError, match="Duplicate study_participant_ids"):
            CfgFileStudyConfig(**base_config)

    def test_valid_duplicate_participant_ids_across_studies(self, base_config):
        """Test that empty participant_ids list is allowed (common case)"""
        # Empty list is valid
        config = CfgFileStudyConfig(**base_config)
        assert config.study_participant_ids == []

        # Unique IDs are valid
        base_config["study_participant_ids"] = ["user1", "user2"]
        config = CfgFileStudyConfig(**base_config)
        assert config.study_participant_ids == ["user1", "user2"]

    def test_date_order_validation(self, base_config):
        """Test that start date must be before end date"""
        base_config["data_collection_start"] = "2024-12-31T23:59:59Z"
        base_config["data_collection_end"] = "2024-01-01T00:00:00Z"
        with pytest.raises(ValueError, match="must be before"):
            CfgFileStudyConfig(**base_config)

    def test_name_short_validation(self, base_config):
        """Test name_short character and length restrictions"""
        # Test invalid characters
        base_config["name_short"] = "Test-Study"
        with pytest.raises(ValueError, match="can only contain lowercase letters"):
            CfgFileStudyConfig(**base_config)

        # Test too short
        base_config["name_short"] = "a"
        with pytest.raises(ValueError, match="must be at least 2 characters"):
            CfgFileStudyConfig(**base_config)

    def test_datetime_tz_aware(self, base_config):
        """Test that datetimes are properly converted to timezone-aware"""
        config = CfgFileStudyConfig(**base_config)
        assert config.data_collection_start.tzinfo is not None
        assert config.data_collection_end.tzinfo is not None
        assert config.data_collection_start.tzinfo == timezone.utc

    def test_allow_unlisted_participants_with_participant_ids(self, base_config):
        """Test configuration with allow_unlisted_participants=False"""
        base_config["allow_unlisted_participants"] = False
        base_config["study_participant_ids"] = ["user1", "user2"]

        config = CfgFileStudyConfig(**base_config)
        assert config.allow_unlisted_participants is False
        assert config.study_participant_ids == ["user1", "user2"]
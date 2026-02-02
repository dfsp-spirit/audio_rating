# config/study_config.py -- Parser for study configuration files in JSON or YAML format
from typing import List, Optional
from pydantic import BaseModel, field_validator, model_validator
import yaml
import json
from pathlib import Path
import re
from datetime import datetime, timezone

class CfgFileSong(BaseModel):
    media_url: str
    display_name: str

    @model_validator(mode='after')
    def set_display_name_from_media_url(self):
        if not self.display_name and self.media_url:
            # Extract a nice display name from the URL
            name = self.media_url.split('/')[-1]  # Get filename from path or url
            name = name.rsplit('.', 1)[0] if '.' in name else name  # Remove extension
            self.display_name = name
        return self


class CfgFileRatingDimension(BaseModel):
    dimension_title: str
    num_values: int
    description: Optional[str] = None

    @model_validator(mode='after')
    def validate_num_values(self):
        if self.num_values < 2:
            raise ValueError(f'num_values for dimension "{self.dimension_title}" must be at least 2')
        if self.num_values > 20:
            raise ValueError(f'num_values for dimension "{self.dimension_title}" cannot exceed 20')
        return self

    @model_validator(mode='after')
    def fill_description_from_title_if_missing(self):
        if not self.description:
            self.description = self.dimension_title
        return self


class CfgFileStudyConfig(BaseModel):
    name: str
    name_short: str
    description: Optional[str] = None
    songs_to_rate: List[CfgFileSong]
    rating_dimensions: List[CfgFileRatingDimension]
    study_participant_ids: List[str] = []
    allow_unlisted_participants: bool = True
    data_collection_start: datetime  # Changed from str to datetime
    data_collection_end: datetime    # Changed from str to datetime

    @field_validator('name_short')
    @classmethod
    def validate_name_short(cls, v):
        if not v:
            raise ValueError('name_short cannot be empty')

        # Check for URL-friendly characters only: lowercase a-z, numbers 0-9, underscore
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError(
                f'name_short "{v}" can only contain lowercase letters (a-z), numbers (0-9), and underscores (_). '
                f'No uppercase letters, spaces, hyphens, or special characters allowed.'
            )

        # Check length
        if len(v) < 2:
            raise ValueError(f'name_short "{v}" must be at least 2 characters long')
        if len(v) > 50:
            raise ValueError(f'name_short "{v}" cannot exceed 50 characters')

        return v

    @field_validator('data_collection_start', 'data_collection_end', mode='before')
    @classmethod
    def parse_iso8601_datetime(cls, v):
        """Parse ISO 8601 string to datetime object"""
        if isinstance(v, str):
            try:
                # Parse ISO 8601 string
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))

                # Ensure it's timezone-aware
                if dt.tzinfo is None:
                    # If no timezone info, assume UTC
                    dt = dt.replace(tzinfo=timezone.utc)

                return dt
            except ValueError:
                # Check format before attempting to parse
                iso8601_regex = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$'
                if not re.match(iso8601_regex, v):
                    raise ValueError(
                        f'Date "{v}" is not in valid ISO 8601 format '
                        f'(e.g., 2024-01-01T00:00:00Z or 2024-01-01T00:00:00+00:00)'
                    )
                raise
        return v

    @field_validator('songs_to_rate')
    @classmethod
    def validate_songs_to_rate(cls, v):
        """Ensure songs_to_rate is not empty and has unique entries"""
        if not v:
            raise ValueError('songs_to_rate cannot be empty')

        # Check for duplicate media_url values
        media_urls = [song.media_url for song in v]
        if len(media_urls) != len(set(media_urls)):
            duplicates = [url for url in media_urls if media_urls.count(url) > 1]
            raise ValueError(f'Duplicate media_url found in songs_to_rate: {set(duplicates)}')

        # Check for duplicate display_name values
        display_names = [song.display_name for song in v]
        if len(display_names) != len(set(display_names)):
            duplicates = [name for name in display_names if display_names.count(name) > 1]
            raise ValueError(f'Duplicate display_name found in songs_to_rate: {set(duplicates)}')

        return v

    @field_validator('rating_dimensions')
    @classmethod
    def validate_rating_dimensions(cls, v):
        """Ensure rating_dimensions is not empty and has unique entries"""
        if not v:
            raise ValueError('rating_dimensions cannot be empty')

        # Check for duplicate dimension_title values
        dimension_titles = [dim.dimension_title for dim in v]
        if len(dimension_titles) != len(set(dimension_titles)):
            duplicates = [title for title in dimension_titles if dimension_titles.count(title) > 1]
            raise ValueError(f'Duplicate dimension_title found in rating_dimensions: {set(duplicates)}')

        return v

    @field_validator('study_participant_ids')
    @classmethod
    def validate_study_participant_ids(cls, v):
        """Ensure study_participant_ids has unique entries"""
        # This list can be empty, but if it has entries, they should be unique

        # Check for duplicate participant IDs
        if len(v) != len(set(v)):
            duplicates = [pid for pid in v if v.count(pid) > 1]
            raise ValueError(f'Duplicate study_participant_ids found: {set(duplicates)}')

        return v

    @model_validator(mode='after')
    def validate_date_order(self):
        """Ensure start date is before end date"""
        if self.data_collection_start and self.data_collection_end:
            if self.data_collection_start >= self.data_collection_end:
                raise ValueError(
                    f'data_collection_start ({self.data_collection_start}) '
                    f'must be before data_collection_end ({self.data_collection_end})'
                )
        return self


class CfgFileStudiesConfig(BaseModel):
    studies: List[CfgFileStudyConfig]

def load_studies_config(config_path: str) -> CfgFileStudiesConfig:
    """Load studies configuration from YAML or JSON file"""

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Studies configuration file not found at '{config_path}'")

    if config_path.suffix in ['.yaml', '.yml']:
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
    elif config_path.suffix == '.json':
        with open(config_path, 'r') as f:
            data = json.load(f)
    else:
        raise ValueError(f"Unsupported config file format: {config_path.suffix}")

    return CfgFileStudiesConfig(**data)
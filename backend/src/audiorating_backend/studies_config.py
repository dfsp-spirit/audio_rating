# config/study_config.py -- Parser for study configuration files in JSON or YAML format
from typing import List, Optional
from pydantic import BaseModel, validator, model_validator
import yaml
import json
from pathlib import Path
import re

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


class CfgFileStudyConfig(BaseModel):
    name: str
    name_short: str
    description: Optional[str] = None
    songs_to_rate: List[CfgFileSong]
    rating_dimensions: List[CfgFileRatingDimension]
    allow_unlisted_participants: bool = True
    study_participant_ids: List[str] = []

    @validator('name_short')
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
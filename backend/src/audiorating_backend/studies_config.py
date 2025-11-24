# config/study_config.py
from typing import List, Optional
from pydantic import BaseModel, validator
import yaml
import json
from pathlib import Path
import re


class StudyConfig(BaseModel):
    name: str
    name_short: str
    description: Optional[str] = None
    songs_to_rate: List[str]  # Simplified - will be converted to SongConfig that holds more details
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



class StudiesConfig(BaseModel):
    studies: List[StudyConfig]

def load_studies_config(config_path: str) -> StudiesConfig:
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

    return StudiesConfig(**data)
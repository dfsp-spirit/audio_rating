from pathlib import Path
from collections import defaultdict
from .parsers.studies_config import load_studies_config, CfgFileStudiesConfig

def check_frontend_audio_files(frontend_dir: str, studies_config_json_file: str) -> bool:
    """
    Checks if the audio files specified in the studies_config_json_file exist in the frontend_dir.

    Args:
        studies_config_json_file: Path to the studies configuration JSON/YAML file
        frontend_dir: Path to the frontend directory containing audio files

    Returns:
        True if all files exist, False otherwise
    """
    # Check whether studies_config_json_file is a file and exists
    config_path = Path(studies_config_json_file)
    if not config_path.exists():
        print(f"ERROR: Studies configuration file '{studies_config_json_file}' does not exist")
        return False
    if not config_path.is_file():
        print(f"ERROR: Studies configuration path '{studies_config_json_file}' is not a file")
        return False

    cfg: CfgFileStudiesConfig = load_studies_config(studies_config_json_file)

    # Convert frontend_dir to absolute path for consistency
    frontend_path = Path(frontend_dir).resolve()

    if not frontend_path.exists():
        print(f"ERROR: Frontend directory '{frontend_dir}' does not exist")
        return False

    if not frontend_path.is_dir():
        print(f"ERROR: Frontend path '{frontend_dir}' is not a directory")
        return False

    # Track files per study for reporting
    study_stats = {}
    missing_files = []
    found_files = []

    for study in cfg.studies:
        study_name = study.name_short
        study_stats[study_name] = {
            'total': len(study.songs_to_rate),
            'found': 0,
            'missing': 0,
            'missing_files': []
        }

        for song in study.songs_to_rate:
            # Get the media_url (could be a filename or full path)
            media_file = song.media_url

            # Create full path by joining with frontend_dir
            # Remove any leading slashes to avoid treating as absolute path
            media_file_clean = media_file.lstrip('/\\')
            audio_file_path = frontend_path / media_file_clean

            # Check if file exists
            if not audio_file_path.exists():
                study_stats[study_name]['missing'] += 1
                missing_files.append({
                    'study': study_name,
                    'file': media_file,
                    'path': str(audio_file_path)
                })
                study_stats[study_name]['missing_files'].append(media_file)

            elif not audio_file_path.is_file():
                print(f"WARNING: Path '{audio_file_path}' exists but is not a file (might be a directory)")
                # Still count as missing since we need a file
                study_stats[study_name]['missing'] += 1
                missing_files.append({
                    'study': study_name,
                    'file': media_file,
                    'path': str(audio_file_path),
                    'note': 'exists but is not a file'
                })
                study_stats[study_name]['missing_files'].append(media_file)
            else:
                study_stats[study_name]['found'] += 1
                found_files.append({
                    'study': study_name,
                    'file': media_file
                })

    # Print summary header
    print("\n" + "="*70)
    print("AUDIO FILES VERIFICATION REPORT")
    print("="*70)
    print(f"Frontend directory: {frontend_path}")
    print(f"Studies config file checked: {config_path.resolve()}")
    print("-"*70)

    # Print summary table
    print(f"\n{'Study':<30} {'Found':<8} {'Expected':<8} {'Status':<10}")
    print("-" * 56)

    all_present = True
    studies_with_all_files = []

    for study_name, stats in study_stats.items():
        if stats['missing'] == 0:
            status = "✓ ALL GOOD"
            studies_with_all_files.append(study_name)
        else:
            status = f"✗ MISSING {stats['missing']}"
            all_present = False

        percentage = (stats['found'] / stats['total']) * 100 if stats['total'] > 0 else 0
        print(f"{study_name[:30]:<30} {stats['found']:<8} {stats['total']:<8} {status:<10} ({percentage:.1f}%)")

    print("-" * 56)

    # Also check whether any study has 0 files specified, which might indicate a misconfiguration
    all_studies_specify_files = True
    for study_name, stats in study_stats.items():
        if stats['total'] == 0:
            print(f"⚠️ WARNING: Study '{study_name}' has no audio files specified. Please check if this is intentional or a misconfiguration.")
            all_studies_specify_files = False

    # Print detailed missing files report if there are any issues
    if missing_files:
        print("\n" + "="*70)
        print("DETAILED MISSING FILES REPORT")
        print("="*70)

        # Group by study for better readability
        files_by_study = defaultdict(list)
        for item in missing_files:
            files_by_study[item['study']].append(item)

        for study_name, files in files_by_study.items():
            print(f"\n📁 Study '{study_name}': {len(files)} missing file(s)")
            for item in files:
                note = f" ({item.get('note', '')})" if 'note' in item else ""
                print(f"  • {item['file']}{note}")
                print(f"    Expected at: {item['path']}")

    note_msg : str = "NOTE: You should run this command for both the backend studies_config.json file and the frontend studies_config.json file (or ensure they are identical, e.g., via `cmp` or `diff`)."

    if all_present and all_studies_specify_files:
        print("\n✅ SUCCESS: All audio files exist!")
        print(f"{note_msg}")
        print("="*70)
        return True
    else:
        if not all_present:
            print("\n❌ FAILURE: Some audio files are missing. Please check the report above.")
            print(f"{note_msg}")
            print("="*70)
        if not all_studies_specify_files:
            print("\n⚠️ WARNING: Some studies have no audio files specified. Please check the report above.")
            print(f"{note_msg}")
            print("="*70)
        return False
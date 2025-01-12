#!/usr/bin/env python3

import os
import argparse
import logging
import re
from typing import List, Dict, Optional, Tuple
from tvdb_v4_official import TVDB
from colorama import init, Fore, Style

# Configuration
API_KEY = os.getenv("TVDB_API_KEY", "")
LANG = os.getenv("TVDB_EPISODE_LANG", "eng")

SUPPORTED_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".flv", ".wmv"}
PLACEHOLDER_EXTENSION = ".placeholder"
LOG_COLORS = {
    logging.WARNING: Fore.YELLOW,
    logging.ERROR: Fore.RED,
}
DRY_RUN = False

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to logging levels."""
    def format(self, record):
        log_level_color = LOG_COLORS.get(record.levelno, Fore.WHITE)
        message = super().format(record)
        level_name = record.levelname
        colored_level_name = f"{log_level_color}{level_name}{Style.RESET_ALL}"
        return message.replace(level_name, colored_level_name)


def fetch_series(series_id: int) -> Dict:
    """Fetch series details from TheTVDB based on the series ID."""
    try:
        logging.debug(f"Fetching details for series ID {series_id} in lang {LANG}")
        series = tvdb.get_series_translation(series_id, LANG)
        logging.info(f"Series name retrieved: {series['name']}")
        return series
    except Exception as e:
        logging.error(f"Error fetching series ID: {e}")
        raise

def fetch_episodes(series_id: int) -> List[Dict]:
    """Fetch episodes from TheTVDB based on the series ID."""
    try:
        episodes = tvdb.get_series_episodes(series_id, lang=LANG)
        if not episodes or 'episodes' not in episodes:
            raise ValueError(f"No episodes found for series ID '{series_id}'.")
        logging.debug(f"Episodes retrieved: {len(episodes['episodes'])}")
        return episodes['episodes']
    except Exception as e:
        logging.error(f"Error fetching episode data: {e}")
        raise

def rename_files(series_id: int, directory: str = '.', season: Optional[int] = None, force: bool = False) -> None:
    """Rename files in the directory based on TheTVDB metadata."""
    if not os.path.exists(directory):
        logging.error(f"Directory '{directory}' does not exist.")
        return

    series_name = fetch_series(series_id)['name']
    series_episodes = fetch_episodes(series_id)

    # Filter episodes for the specified season
    episodes = [ep for ep in series_episodes if ep['seasonNumber'] == season] if season is not None else series_episodes
    if not episodes:
        logging.error(f"No episodes found for series ID {series_id} in season {season}.")
        return
    logging.info(f"Episodes found for {'all seasons' if season is None else f'season {season}'}: {len(episodes)}")

    # The calculation fails with some series where the numbering is not sequential,
    # maybe due to specials being part  of the main season
    season_start = calculate_season_start(series_episodes, season) if not force else 1
    season_end = season_start + len(episodes) - 1
    logging.debug(f"Absolute episode numbering for Season {season} ends at: {season_end}")

    episodes.sort(key=lambda ep: ep['number'])
    episode_map = {ep['number']: ep for ep in episodes}

    all_files = [f for f in os.listdir(directory) if is_supported_file(f)]
    if not all_files:
        logging.info("No files found in the directory. Nothing to do.")
        return

    file_episode_mapping = filter_valid_episode_numbers(all_files, series_name, season_start, season_end, season)
    if not file_episode_mapping:
        logging.info(f"No episodes in the directory belong to Season {season}.")
        return

    file_episode_numbers = set(file_episode_mapping.values())
    missing_episodes = sorted(set(range(season_start, season_end + 1)) - file_episode_numbers)
    logging.debug(f"Missing episodes: {missing_episodes}")

    if missing_episodes:
        logging.info(f"Missing episodes found")
        create_placeholder_files(directory, missing_episodes, series_name)

    # Files to process: exclude already correctly renamed files
    files_to_process = [f for f in all_files if not is_renamed_file(f, series_name, season)]
    files_to_process.extend([f"{series_name} {episode_number}{PLACEHOLDER_EXTENSION}" for episode_number in missing_episodes])
    files_to_process.sort(key=sort_by_season_and_episode)

    # Reset episode numbering if the files do not start from 1
    if file_episode_numbers and min(file_episode_numbers) != 1 and confirm_reset_numbering():
        files_to_process = reset_episode_numbering(files_to_process, directory, series_name, episode_map)
    else:
        files_to_process = sorted(
            [f for f in os.listdir(directory)
             if (is_supported_file(f) and not is_renamed_file(f, series_name, season)) or f.endswith(PLACEHOLDER_EXTENSION)],
            key=sort_by_season_and_episode
        )

    logging.info("--- Starting the renaming process ---")
    for filename in files_to_process:
        file_path = os.path.join(directory, filename)
        base_filename, file_extension = os.path.splitext(filename)

        episode_number = file_episode_mapping.get(filename)
        if episode_number is None:
            episode_number = extract_episode_number(filename, series_name)
            if episode_number is None or episode_number == -1:
                logging.warning(f"Skipping {filename}: Could not determine episode number.")
                continue

        if episode_number not in episode_map:
            logging.warning(f"Skipping {filename}: No match found for episode number {episode_number}.")
            continue

        episode = episode_map[episode_number]
        new_filename = generate_new_filename(series_name, episode, file_extension)
        new_path = os.path.join(directory, new_filename)

        if os.path.basename(new_path) == filename:
            logging.info(f"{Fore.LIGHTYELLOW_EX}Skipping{Style.RESET_ALL} {filename}: Already correctly named.")
            continue

        if DRY_RUN:
            print(f"Would rename: {filename} -> {new_filename}")
        else:
            try:
                os.rename(file_path, new_path)
                logging.info(f"{Fore.GREEN}Renamed{Style.RESET_ALL}: {filename} -> {new_filename}")
            except OSError as e:
                logging.error(f"Failed to rename {filename} to {new_filename}: {e}")

    remove_placeholder_files(directory)

def generate_new_filename(series_name: str, episode: Dict, file_extension: str) -> str:
    """
    Generate the new filename in the format: SeriesName SXXEYY - EpisodeTitle.ext.
    If the episode title is missing, it uses: SeriesName SXXEYY.ext.
    """
    formatted_season = f"S{episode['seasonNumber']:02d}" if episode['seasonNumber'] is not None else ""
    formatted_episode = f"E{episode['number']:02d}" if episode['seasonNumber'] is not None else f"{episode['number']:02d}"
    episode_name = f" - {episode['name']}" if episode.get('name') else ""
    return f"{series_name} {formatted_season}{formatted_episode}{episode_name}{file_extension}"

def extract_episode_number(filename: str, series_name: str) -> Optional[int]:
    """Extract episode number from a filename, as accurately as possible."""
    explicit_patterns = [
        r'(?:ep|episode|s\d+\s?e)[\s._-]*(\d+)',
    ]
    unsupported_patterns = [
        # Multi-episode files (e.g., "S01E03-04")
        r'E?(\d+)[-_]E?(\d+)',
        # Episode numbers with a dot (e.g., "S01E03.04")
        r'(\d+)[.](\d+)',
    ]

    for pattern in unsupported_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            logging.warning(f"Unsupported pattern found in {filename}: {match.group(0)}. Skipping file.")
            return -1

    for pattern in explicit_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            episode_number = int(match.group(1))
            logging.debug(f"Extracted explicit episode number: {episode_number} from {filename}")
            return episode_number

    # Remove the series name from the filename to avoid false positives
    # Use regex to handle variations in spacing, underscores, hyphens, etc.
    series_name_pattern = re.compile(re.escape(series_name), re.IGNORECASE)
    filename_without_series = series_name_pattern.sub('', filename).strip()

    # Extract the first number after the series name
    match = re.search(r'[\s._-]*(\d+)', filename_without_series)
    if match:
        episode_number = int(match.group(1))
        logging.debug(f"Extracted episode number: {episode_number} from {filename} (series: {series_name})")
        return episode_number

    # Finally, check for standalone numbers as a fallback. Use the last number
    all_numbers = re.findall(r'\d+', filename)
    if all_numbers:
        episode_number = int(all_numbers[-1])
        logging.debug(f"Extracted episode number: {episode_number} from {filename}")
        return episode_number

    logging.warning(f"Could not extract episode number from {filename}")
    return None

def sort_by_season_and_episode(file_name: str) -> Tuple[int, int]:
    """Generate a sorting key for filenames based on season and episode numbers."""
    pattern_match = re.search(r'S(\d+)E(\d+)', file_name)
    if pattern_match:
        return 0, int(pattern_match.group(2))
    numbers = list(map(int, re.findall(r'\d+', file_name)))
    return (0, *numbers) if numbers else (0, 0)

def is_supported_file(file_name: str) -> bool:
    """Check if a file has a supported video extension."""
    return os.path.splitext(file_name)[1].lower() in SUPPORTED_EXTENSIONS

def is_renamed_file(file_name: str, series_name: str, season: Optional[int]) -> bool:
    """
    Check if a file is already renamed correctly according to the folder's season.
    The filename must match the pattern: SeriesName SXXEYY - EpisodeName.ext,
    and the season number in the filename must match the folder's season.
    """
    safe_series_name = re.escape(series_name)

    pattern = rf'^{safe_series_name}\sS(\d+)E\d+.*\.\w+$'
    match = re.match(pattern, file_name, re.IGNORECASE)
    if not match:
        return False

    filename_season = int(match.group(1))
    if season is not None and filename_season != season:
        logging.debug(f"Skipping {file_name}: Season number mismatch (expected: {season}, found: {filename_season}).")
        return False

    logging.info(f"{Fore.LIGHTYELLOW_EX}Skipping{Style.RESET_ALL} {file_name}: Already correctly named.")
    return True

def confirm_reset_numbering() -> bool:
    """Ask the user for confirmation to reset episode numbering."""
    print(f"{Fore.LIGHTRED_EX}The episode numbering does not start from 1, which may cause issues with proper renaming.{Style.RESET_ALL}")
    print("Only as many files will be renamed as the number of episodes in the TVDB list.")
    if not DRY_RUN:
        print(f"{Fore.LIGHTRED_EX}If you decide to skip this step, it could make unwanted changes!{Style.RESET_ALL}")

    response = input(f"{Fore.LIGHTGREEN_EX}Do you want to reset the episode numbering to match the TVDB series? (YES/no):{Style.RESET_ALL} ").strip().lower()
    response = response if response else "y"
    logging.info(f"User response: {response}")
    return response in {"yes", "y"}

def reset_episode_numbering(files: List[str], directory: str, series_name: str, episode_map: Dict[int, Dict]) -> List[str]:
    """Reset episode numbering starting from 1."""
    new_episode_number = 1
    # Needed for Dry-run correctness
    new_files = []
    for idx, filename in enumerate(files):
        file_path = os.path.join(directory, filename)
        base_filename, file_extension = os.path.splitext(filename)

        if new_episode_number > max(episode_map.keys()):
            logging.info("Reached the maximum episode number for the season in the TVDB list. Stopping.")
            break

        # Simulate an episode object for the reset numbering
        episode = {'seasonNumber': None, 'number': new_episode_number, 'name': ''}
        new_filename = generate_new_filename(series_name, episode, file_extension)
        new_path = os.path.join(directory, new_filename)
        new_files.append(new_filename)

        if DRY_RUN:
            print(f"Would rename: {filename} -> {new_filename}")
        else:
            try:
                os.rename(file_path, new_path)
                logging.info(f"{Fore.GREEN}Renamed{Style.RESET_ALL}: {filename} -> {new_filename}")
            except OSError as e:
                logging.error(f"Failed to rename {filename} to {new_filename}: {e}")

        new_episode_number += 1

    return new_files

def filter_valid_episode_numbers(files: List[str], series_name: str, season_start: int, season_end: int, season: Optional[int]) -> Dict[str, int]:
    """
    Extract and validate episode numbers from filenames.
    Returns a mapping from filenames to episode numbers within the specified season range.
    """
    valid_episode_numbers = {}
    for filename in files:
        if is_renamed_file(filename, series_name, season):
            logging.debug(f"Filtering out {filename}: Already correctly named.")
            continue

        episode_number = extract_episode_number(filename, series_name)
        if episode_number is None or episode_number == -1:
            continue
        if episode_number < season_start or episode_number > season_end:
            logging.warning(f"Skipping {filename}, because the episode number is outside the range for the season.")
            continue
        valid_episode_numbers[filename] = episode_number
    return valid_episode_numbers

def calculate_season_start(all_episodes: List[Dict], season: int) -> int:
    """
    Calculate the starting absolute episode number for a season based on previous seasons' total.
    Also logs the total number of episodes per season for debugging purposes.
    """
    if season in [None, 0, 1]:
        logging.debug("Season 1 and specials start at episode 1.")
        return 1

    seasons = {}
    for ep in all_episodes:
        season_num = ep['seasonNumber']
        if season_num not in seasons:
            seasons[season_num] = 0
        seasons[season_num] += 1

    for season_num, total_eps in sorted(seasons.items()):
        logging.debug(f"Season {season_num}: {total_eps} episodes{' - IGNORED' if season_num == 0 else ''}")

    previous_season_episodes = [ep for ep in all_episodes if season > ep['seasonNumber'] > 0]
    season_start = sum(1 for _ in previous_season_episodes) + 1
    logging.debug(f"Absolute episode numbering for Season {season} starts at {season_start}.")

    return season_start

def create_placeholder_files(directory: str, missing_episodes: List[int], series_name: str) -> None:
    """Create placeholder files for missing episodes."""
    for episode_number in missing_episodes:
        # Simulate an episode object for the placeholder
        episode = {'seasonNumber': None, 'number': episode_number, 'name': ''}
        placeholder_filename = generate_new_filename(series_name, episode, PLACEHOLDER_EXTENSION)
        placeholder_path = os.path.join(directory, placeholder_filename)
        if not os.path.exists(placeholder_path):
            if DRY_RUN:
                logging.info(f"Would create placeholder: {placeholder_filename}")
            else:
                try:
                    with open(placeholder_path, "w") as f:
                        f.write("")
                    logging.info(f"Created placeholder: {placeholder_filename}")
                except OSError as e:
                    logging.error(f"Failed to create placeholder {placeholder_filename}: {e}")

def remove_placeholder_files(directory: str) -> None:
    """Remove placeholder files from the directory."""
    if DRY_RUN:
        logging.info(f"Would remove placeholders now")
        return

    for filename in os.listdir(directory):
        if filename.endswith(PLACEHOLDER_EXTENSION):
            placeholder_path = os.path.join(directory, filename)
            try:
                os.remove(placeholder_path)
                logging.info(f"Removed placeholder: {filename}")
            except OSError as e:
                logging.error(f"Failed to remove placeholder {filename}: {e}")


def main():
    """Main function to run the script."""
    global DRY_RUN

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    parser = argparse.ArgumentParser(description="Rename TV episode filenames based on TheTVDB metadata.")
    parser.add_argument("--series-id", type=int, required=True, help="TheTVDB series ID.")
    parser.add_argument("--season", type=int, help="Season number.")
    parser.add_argument("--directory", default=".", help="Directory containing the files to rename.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without renaming files.")
    parser.add_argument("--force", action="store_true", help="Force renaming, starting from episode 1 and accounting for missing episodes.")

    args = parser.parse_args()
    DRY_RUN = args.dry_run

    if args.force:
        logging.info(f"Force mode enabled. Renaming will start from episode 1.")

    if not args.season:
        if re.match(r"Season \d+", str(args.directory)):
            args.season = int(re.search(r"Season (\d+)", str(args.directory)).group(1))
            logging.info(f"Season number detected from directory name: {args.season}")
        elif re.match(r"Specials", os.path.basename(args.directory)):
            args.season = 0
            logging.info(f"Specials (0) season detected from directory name.")
    elif not args.season and args.directory == ".":
        current_directory = os.path.basename(os.getcwd())
        if re.match(r"Season \d+", current_directory):
            args.season = int(re.search(r"Season (\d+)", current_directory).group(1))
            logging.info(f"Season number detected from current directory name: {args.season}")

    logging.info("Starting the script in dry-run mode." if DRY_RUN else "Starting the script.")
    logging.debug(f"Arguments: {args}")

    rename_files(
        series_id=args.series_id,
        directory=args.directory,
        season=args.season,
        force=args.force
    )

if __name__ == "__main__":
    init()
    tvdb = TVDB(API_KEY)
    main()

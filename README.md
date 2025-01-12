# TVDBRenamer

This script renames TV episode files in a directory based on metadata from TheTVDB and makes the format compatible with Jellyfin.
It supports various video file extensions and can handle multiple seasons and episodes.

Series must be sorted into directories by season, e.g. `Season 1`, `Season 2`, etc.

## Prerequisites

- Python 3.x
- `tvdb_v4_official` library
- `colorama` library
- TheTVDB API key (set as an environment variable `TVDB_API_KEY`)

## Installation

1. Clone the repository or download the script.
2. Install the required libraries:

`pip install tvdbv4official colorama`

3. Set your TheTVDB API key as an environment variable:

` export TVDBAPIKEY="yourapikey_here"`

## Usage

Run the script with the following command:

`python3 rename_episodes.py --series-id [--season ] [--directory ] [--dry-run] [--force]`

### Arguments

- `--series-id`: The ID of the series on TheTVDB (required).
- `--season`: The season number to rename episodes for (optional). If not provided, the script will attempt to detect the season from the directory name.
- `--directory`: The directory containing the episode files (defaults to the current directory).
- `--dry-run`: Preview changes without renaming files.
- `--force`: Force renaming, starting from episode 1.

### Example

To rename episodes in the current directory for season 1 of a series with ID 12345:

`python3 rename_episodes.py --series-id 12345 --season 1`

To preview changes without renaming files and detect the season from the directory name:

`python3 rename_episodes.py --series-id 12345 --directory='Season 1' --dry-run`

To force renaming starting from episode 1:

`python3 rename_episodes.py --series-id 12345 --season 1 --force`

## Placeholder Files

If the script detects missing episodes, it will create placeholder files with the extension `.placeholder` to ensure correct 
episode numbering. These files will be removed again at the end.

## Notes

- The script assumes that the episode numbers in the filenames are sequential and start from 1. If this is not the case, you may need to use the `--force` option.
- The script will skip files that are already correctly named.

## License

EUPL-1.2 https://interoperable-europe.ec.europa.eu/collection/eupl/eupl-text-eupl-12
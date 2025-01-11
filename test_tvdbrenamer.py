import unittest
from tvdbrenamer import (
    extract_episode_number,
    sort_by_season_and_episode,
    is_supported_file,
    is_renamed_file,
    generate_new_filename,
)

class TestEpisodeRenaming(unittest.TestCase):
    def test_extract_episode_number(self):
        # Test explicit patterns
        self.assertEqual(extract_episode_number("SeriesName S01E01.mkv", "SeriesName"), 1)
        self.assertEqual(extract_episode_number("SeriesName Episode 02.mkv", "SeriesName"), 2)
        self.assertEqual(extract_episode_number("SeriesName 03.mkv", "SeriesName"), 3)

        # Test unsupported patterns
        self.assertEqual(extract_episode_number("SeriesName 04-05.mkv", "SeriesName"), -1)  # Multi-episode
        self.assertEqual(extract_episode_number("SeriesName S01E04-05.mkv", "SeriesName"), -1)  # Multi-episode
        self.assertEqual(extract_episode_number("SeriesName S01E06.07.mkv", "SeriesName"), -1)  # Dot-separated

        # Test fallback to standalone numbers
        self.assertEqual(extract_episode_number("SeriesName 08.mkv", "SeriesName"), 8)
        self.assertEqual(extract_episode_number("SeriesName 09 - Episode Title.mkv", "SeriesName"), 9)

    def test_sort_by_season_and_episode(self):
        # Test sorting with season and episode
        self.assertEqual(sort_by_season_and_episode("SeriesName S01E01.mkv"), (1, 1))
        self.assertEqual(sort_by_season_and_episode("SeriesName S02E03.mkv"), (2, 3))

        # Test sorting with standalone numbers
        self.assertEqual(sort_by_season_and_episode("SeriesName 04.mkv"), (0, 4))
        self.assertEqual(sort_by_season_and_episode("SeriesName 05 - Episode Title.mkv"), (0, 5))

    def test_is_supported_file(self):
        # Test supported extensions
        self.assertTrue(is_supported_file("SeriesName.mkv"))
        self.assertTrue(is_supported_file("SeriesName.mp4"))
        self.assertTrue(is_supported_file("SeriesName.avi"))

        # Test unsupported extensions
        self.assertFalse(is_supported_file("SeriesName.txt"))
        self.assertFalse(is_supported_file("SeriesName.jpg"))
        self.assertFalse(is_supported_file("README.md"))

    def test_is_renamed_file(self):
        # Test correctly renamed files
        self.assertTrue(is_renamed_file("SeriesName S01E01 - Pilot.mkv", "SeriesName", 1))
        self.assertTrue(is_renamed_file("SeriesName S02E03 - Episode Name.mp4", "SeriesName", 2))

        # Test files with incorrect season numbers
        self.assertFalse(is_renamed_file("SeriesName S03E01 - Pilot.mkv", "SeriesName", 2))  # Wrong season
        self.assertFalse(is_renamed_file("SeriesName S01.mkv", "SeriesName", 1))  # Missing episode name

        # Test files without season number
        self.assertFalse(is_renamed_file("SeriesName 01.mkv", "SeriesName", 1))  # No season number
        self.assertFalse(is_renamed_file("SeriesName 01 - Pilot.mkv", "SeriesName", 1))  # No season number

    def test_generate_new_filename(self):
        # Test filename generation with episode title
        episode = {'seasonNumber': 1, 'number': 1, 'name': "Pilot"}
        self.assertEqual(generate_new_filename("SeriesName", episode, ".mkv"), "SeriesName S01E01 - Pilot.mkv")

        # Test filename generation without episode title
        episode = {'seasonNumber': 2, 'number': 3, 'name': ""}
        self.assertEqual(generate_new_filename("SeriesName", episode, ".mp4"), "SeriesName S02E03.mp4")

        # Test filename for a special (e.g., movie)
        episode = {'seasonNumber': None, 'number': 1, 'name': ""}
        self.assertEqual(generate_new_filename("SeriesName", episode, ".mkv"), "SeriesName 01.mkv")

if __name__ == "__main__":
    unittest.main()
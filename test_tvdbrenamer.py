import unittest
from tvdbrenamer import extract_episode_number, sort_by_season_and_episode

class TestEpisodeRenaming(unittest.TestCase):
    def test_extract_episode_number(self):
        # Test explicit patterns
        self.assertEqual(extract_episode_number("SeriesName S01E01.mkv", "SeriesName"), 1)
        self.assertEqual(extract_episode_number("SeriesName Episode 02.mkv", "SeriesName"), 2)
        self.assertEqual(extract_episode_number("SeriesName 03.mkv", "SeriesName"), 3)

        # Test unsupported patterns
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

if __name__ == "__main__":
    unittest.main()

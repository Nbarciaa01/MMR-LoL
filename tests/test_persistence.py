from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from src.lolscout.config import AppConfig, load_config, save_config
from src.lolscout.models import PlayerSummary, RankedEntry
from src.lolscout.scraping_client import ScrapingClient


class PersistenceTests(unittest.TestCase):
    def test_config_uses_database_store_when_configured(self) -> None:
        store = Mock()
        store.load_config.return_value = {
            "default_platform": "EUW1",
            "ranking_players": [["Player", "EUW"]],
        }

        with patch("src.lolscout.config.get_store", return_value=store):
            config = load_config()
            save_config(config)

        self.assertEqual(config.ranking_players, [["Player", "EUW"]])
        store.save_config.assert_called_once_with("EUW1", [["Player", "EUW"]])

    def test_daily_snapshot_uses_database_store_when_configured(self) -> None:
        store = Mock()
        player = PlayerSummary(
            game_name="Player",
            tag_line="EUW",
            summoner_level=100,
            profile_icon_id=1,
            platform="EUW1",
            soloq=RankedEntry(
                queue_type="RANKED_SOLO_5x5",
                tier="GOLD",
                rank="I",
                league_points=50,
                wins=10,
                losses=8,
            ),
        )

        with patch("src.lolscout.scraping_client.get_store", return_value=store):
            ScrapingClient()._append_daily_lp_snapshot(player)

        store.append_snapshot.assert_called_once()
        args = store.append_snapshot.call_args.args
        self.assertEqual(args[:3], ("EUW1", "Player", "EUW"))
        self.assertEqual(args[3]["total_games"], 18)


if __name__ == "__main__":
    unittest.main()

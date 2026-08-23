from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from src.lolscout.web_app import (
    ConfigInput,
    _require_admin,
    _soloq_sort_key,
    privacy,
    terms,
    update_config,
)


class WebAppTests(unittest.TestCase):
    def test_legal_pages_and_security_headers_are_available(self) -> None:
        privacy_response = privacy()
        terms_response = terms()

        self.assertTrue(Path(privacy_response.path).exists())
        self.assertTrue(Path(terms_response.path).exists())

    def test_config_update_requires_admin_token(self) -> None:
        payload = {
            "default_platform": "EUW1",
            "players": [{"game_name": "Player", "tag_line": "EUW"}],
        }
        with patch.dict(os.environ, {"MMRLOL_ADMIN_TOKEN": "secret"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                _require_admin(None)

        self.assertEqual(raised.exception.status_code, 401)

    def test_admin_token_supports_non_ascii_characters(self) -> None:
        with patch.dict(os.environ, {"MMRLOL_ADMIN_TOKEN": "secreto-ñ-🔒"}, clear=False):
            _require_admin("Bearer secreto-ñ-🔒")

    def test_config_update_saves_valid_players(self) -> None:
        payload = {
            "default_platform": "EUW1",
            "players": [{"game_name": "Player", "tag_line": "EUW"}],
        }
        with (
            patch.dict(os.environ, {"MMRLOL_ADMIN_TOKEN": "secret"}, clear=False),
            patch("src.lolscout.web_app._riot_client", return_value=None),
            patch("src.lolscout.web_app.save_config") as save_config,
        ):
            _require_admin("Bearer secret")
            response = update_config(ConfigInput.model_validate(payload), None)

        self.assertEqual(response["players"], 1)
        saved = save_config.call_args.args[0]
        self.assertEqual(saved.ranking_players, [["Player", "EUW"]])

    def test_soloq_ranking_uses_tier_division_and_lp_instead_of_estimated_mmr(self) -> None:
        players = [
            {"player": {"game_name": "Platinum", "estimated_mmr": 1900, "soloq": {
                "tier": "PLATINUM", "rank": "I", "league_points": 99,
            }}},
            {"player": {"game_name": "Emerald", "estimated_mmr": 1500, "soloq": {
                "tier": "EMERALD", "rank": "IV", "league_points": 0,
            }}},
            {"player": {"game_name": "EmeraldHigh", "estimated_mmr": 1400, "soloq": {
                "tier": "EMERALD", "rank": "III", "league_points": 25,
            }}},
        ]

        players.sort(key=_soloq_sort_key, reverse=True)

        self.assertEqual(
            [item["player"]["game_name"] for item in players],
            ["EmeraldHigh", "Emerald", "Platinum"],
        )


if __name__ == "__main__":
    unittest.main()

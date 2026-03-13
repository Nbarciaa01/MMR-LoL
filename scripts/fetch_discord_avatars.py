from __future__ import annotations

import json
import os
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
USER_MAP_PATH = PROJECT_ROOT / "userdc_id.json"
OUTPUT_DIR = PROJECT_ROOT / "discord_avatars"


def load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def build_avatar_url(guild_id: str, user_id: str, bot_token: str) -> str | None:
    response = requests.get(
        f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
        headers={"Authorization": f"Bot {bot_token}"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    member_avatar = payload.get("avatar")
    user = payload.get("user", {})
    user_avatar = user.get("avatar") if isinstance(user, dict) else None

    if member_avatar:
        return f"https://cdn.discordapp.com/guilds/{guild_id}/users/{user_id}/avatars/{member_avatar}.png?size=128"
    if user_avatar:
        return f"https://cdn.discordapp.com/avatars/{user_id}/{user_avatar}.png?size=128"
    return None


def main() -> int:
    load_dotenv()

    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    if not bot_token or not guild_id:
        raise SystemExit("Faltan DISCORD_BOT_TOKEN o DISCORD_GUILD_ID en el entorno o en .env")

    if not USER_MAP_PATH.exists():
        raise SystemExit("No existe userdc_id.json en la raiz del proyecto")

    try:
        user_map = json.loads(USER_MAP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"No se pudo leer userdc_id.json: {exc}") from exc

    if not isinstance(user_map, dict):
        raise SystemExit("userdc_id.json debe ser un objeto JSON clave -> discord_user_id")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for _, raw_user_id in user_map.items():
        user_id = str(raw_user_id).strip()
        if not user_id:
            continue

        avatar_url = build_avatar_url(guild_id, user_id, bot_token)
        if not avatar_url:
            continue

        image_response = requests.get(avatar_url, timeout=10)
        image_response.raise_for_status()
        (OUTPUT_DIR / f"{user_id}.png").write_bytes(image_response.content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import copy
import time
from threading import Lock

import requests
from fastapi import HTTPException


_lock = Lock()
_cached: tuple[float, dict] | None = None


def catalog() -> dict:
    global _cached
    with _lock:
        if _cached and _cached[0] > time.monotonic():
            return copy.deepcopy(_cached[1])
        try:
            response = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=10)
            response.raise_for_status()
            version = response.json()[0]
            base = f"https://ddragon.leagueoflegends.com/cdn/{version}"
            response = requests.get(f"{base}/data/es_ES/champion.json", timeout=10)
            response.raise_for_status()
            champions = [
                {
                    "id": int(item["key"]),
                    "slug": item["id"].lower(),
                    "name": item["name"],
                    "icon_url": f"{base}/img/champion/{item['image']['full']}",
                }
                for item in response.json()["data"].values()
            ]
            payload = {"version": version, "champions": sorted(champions, key=lambda item: item["name"])}
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            if _cached:
                return copy.deepcopy(_cached[1])
            raise HTTPException(status_code=503, detail="No se pudieron cargar los recursos de campeones.") from exc
        _cached = (time.monotonic() + 3600, payload)
        return copy.deepcopy(payload)


def profile_icon_url(icon_id: int) -> str | None:
    if icon_id <= 0:
        return None
    try:
        version = catalog()["version"]
    except HTTPException:
        return None
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{icon_id}.png"

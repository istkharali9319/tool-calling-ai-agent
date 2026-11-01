"""Current weather and a short forecast from Open-Meteo (https://open-meteo.com).

Open-Meteo is free for non-commercial use and needs no API key. Results are cached for a few
minutes so repeated questions about the same place don't call the API again.
"""

import threading
import time
from typing import Any

import httpx

from app.config import get_settings
from app.tools import ToolError

# WMO weather interpretation codes used by Open-Meteo.
WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
    "precipitation,weather_code,wind_speed_10m"
)
DAILY_FIELDS = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"


def describe(code: int | None) -> str:
    return WEATHER_CODES.get(code, "Unknown") if code is not None else "Unknown"


class WeatherService:
    def __init__(
        self,
        geocoding_url: str,
        forecast_url: str,
        timeout: float = 10.0,
        temperature_unit: str = "celsius",
        cache_seconds: float = 600,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._geocoding_url = geocoding_url
        self._forecast_url = forecast_url
        self._temperature_unit = temperature_unit
        self._cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        # retries=2 retries failed connections (not HTTP error responses).
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport or httpx.HTTPTransport(retries=2),
            headers={"User-Agent": "ai-business-assistant/1.0"},
        )

    def get_weather(self, location: str) -> dict[str, Any]:
        key = " ".join(location.lower().split())
        with self._lock:
            cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < self._cache_seconds:
            return cached[1]

        place = self._geocode(location)
        forecast = self._get_json(
            self._forecast_url,
            {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": CURRENT_FIELDS,
                "daily": DAILY_FIELDS,
                "timezone": "auto",
                "forecast_days": 3,
                "temperature_unit": self._temperature_unit,
            },
        )
        result = self._format(place, forecast)

        with self._lock:
            self._cache[key] = (time.monotonic(), result)
        return result

    def _geocode(self, location: str) -> dict[str, Any]:
        # The geocoder matches place names only, so "Paris, France" is searched as "Paris"
        # and the part after the comma narrows the results by country or region.
        name, _, qualifier = (part.strip() for part in location.partition(","))
        if not name:
            raise ToolError("Please give a city or place name.")

        data = self._get_json(
            self._geocoding_url, {"name": name, "count": 10, "language": "en", "format": "json"}
        )
        results = data.get("results") or []
        if qualifier:
            q = qualifier.lower()
            results = [
                r for r in results
                if q in (r.get("country") or "").lower()
                or q == (r.get("country_code") or "").lower()
                or q in (r.get("admin1") or "").lower()
            ]
        if not results:
            raise ToolError(f"Could not find a place called '{location}'.")
        return results[0]  # the geocoder ranks by relevance and population

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._http.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise ToolError("The weather service timed out. Please try again.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ToolError("The weather service is unavailable right now.") from exc

    @staticmethod
    def _format(place: dict[str, Any], forecast: dict[str, Any]) -> dict[str, Any]:
        current = forecast.get("current", {})
        units = forecast.get("current_units", {})
        daily = forecast.get("daily", {})
        days = [
            {
                "date": date,
                "condition": describe(code),
                "weather_code": code,
                "temperature_max": t_max,
                "temperature_min": t_min,
                "precipitation_probability": rain,
            }
            for date, code, t_max, t_min, rain in zip(
                daily.get("time", []),
                daily.get("weather_code", []),
                daily.get("temperature_2m_max", []),
                daily.get("temperature_2m_min", []),
                daily.get("precipitation_probability_max", []),
            )
        ]
        return {
            "location": {
                "name": place.get("name"),
                "region": place.get("admin1"),
                "country": place.get("country"),
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "timezone": forecast.get("timezone"),
            },
            "current": {
                "time": current.get("time"),
                "condition": describe(current.get("weather_code")),
                "weather_code": current.get("weather_code"),
                "is_day": bool(current.get("is_day", 1)),
                "temperature": current.get("temperature_2m"),
                "feels_like": current.get("apparent_temperature"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_speed": current.get("wind_speed_10m"),
                "precipitation": current.get("precipitation"),
            },
            "daily": days,
            "units": {
                "temperature": units.get("temperature_2m", "°C"),
                "wind_speed": units.get("wind_speed_10m", "km/h"),
                "precipitation": units.get("precipitation", "mm"),
            },
            "source": "Open-Meteo",
        }


_service: WeatherService | None = None
_service_lock = threading.Lock()


def get_service() -> WeatherService:
    global _service
    with _service_lock:
        if _service is None:
            s = get_settings()
            _service = WeatherService(
                geocoding_url=s.weather_geocoding_url,
                forecast_url=s.weather_forecast_url,
                timeout=s.weather_timeout_seconds,
                temperature_unit=s.weather_temperature_unit,
                cache_seconds=s.weather_cache_seconds,
            )
        return _service


def get_weather(location: str) -> dict[str, Any]:
    return get_service().get_weather(location)

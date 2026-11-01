import httpx
import pytest

from app.services.tool_executor import ToolExecutor
from app.tools import ToolError, weather_tools
from app.tools.weather_tools import WeatherService

GEO_URL = "https://geo.test/search"
FORECAST_URL = "https://forecast.test/forecast"

PLACES = [
    {"name": "Paris", "latitude": 48.85, "longitude": 2.35, "country": "France", "country_code": "FR",
     "admin1": "Île-de-France"},
    {"name": "Paris", "latitude": 33.66, "longitude": -95.56, "country": "United States", "country_code": "US",
     "admin1": "Texas"},
]

FORECAST = {
    "timezone": "Europe/Paris",
    "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h", "precipitation": "mm"},
    "current": {
        "time": "2026-11-01T13:00", "temperature_2m": 12.4, "relative_humidity_2m": 81,
        "apparent_temperature": 10.9, "is_day": 1, "precipitation": 0.2, "weather_code": 61,
        "wind_speed_10m": 14.0,
    },
    "daily": {
        "time": ["2026-11-01", "2026-11-02"],
        "weather_code": [61, 3],
        "temperature_2m_max": [13.0, 14.5],
        "temperature_2m_min": [7.1, 8.0],
        "precipitation_probability_max": [80, 20],
    },
}


def make_service(handler, **kwargs) -> WeatherService:
    return WeatherService(GEO_URL, FORECAST_URL, transport=httpx.MockTransport(handler), **kwargs)


def default_handler(requests: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "geo.test":
            name = request.url.params["name"].lower()
            return httpx.Response(200, json={"results": [p for p in PLACES if p["name"].lower() == name]})
        return httpx.Response(200, json=FORECAST)

    return handler


def test_current_weather_and_forecast():
    requests: list[httpx.Request] = []
    result = make_service(default_handler(requests)).get_weather("Paris")

    assert result["location"]["country"] == "France"
    assert result["current"]["condition"] == "Slight rain"
    assert result["current"]["temperature"] == 12.4
    assert result["units"]["temperature"] == "°C"
    assert [d["condition"] for d in result["daily"]] == ["Slight rain", "Overcast"]
    assert result["daily"][0]["precipitation_probability"] == 80

    forecast_params = requests[1].url.params
    assert forecast_params["latitude"] == "48.85" and forecast_params["timezone"] == "auto"


def test_country_after_comma_picks_the_right_place():
    requests: list[httpx.Request] = []
    result = make_service(default_handler(requests)).get_weather("Paris, Texas")
    assert result["location"]["region"] == "Texas"
    assert requests[0].url.params["name"] == "Paris"  # only the place name goes to the geocoder


def test_unknown_place():
    with pytest.raises(ToolError, match="Could not find"):
        make_service(default_handler([])).get_weather("Atlantis")


def test_results_are_cached():
    requests: list[httpx.Request] = []
    service = make_service(default_handler(requests))
    service.get_weather("Paris")
    service.get_weather("  paris ")
    assert len(requests) == 2  # one geocode + one forecast, then served from cache


def test_cache_can_be_disabled():
    requests: list[httpx.Request] = []
    service = make_service(default_handler(requests), cache_seconds=0)
    service.get_weather("Paris")
    service.get_weather("Paris")
    assert len(requests) == 4


def test_server_error_becomes_tool_error():
    service = make_service(lambda request: httpx.Response(503))
    with pytest.raises(ToolError, match="unavailable"):
        service.get_weather("Paris")


def test_timeout_becomes_tool_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ToolError, match="timed out"):
        make_service(handler).get_weather("Paris")


def test_weather_tool_through_executor(monkeypatch):
    monkeypatch.setattr(weather_tools, "_service", make_service(default_handler([])))

    result = ToolExecutor().execute("get_weather", '{"location": "Paris"}')

    assert result.ok and result.output["current"]["condition"] == "Slight rain"
    assert not ToolExecutor().execute("get_weather", '{"location": ""}').ok

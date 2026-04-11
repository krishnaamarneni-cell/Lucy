"""Lucy skill: weather_openmeteo — Free weather via Open-Meteo API (no auth required)."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# WMO Weather interpretation codes -> descriptions
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _geocode(location: str) -> dict:
    """Resolve a location name to lat/lon using Open-Meteo geocoding."""
    resp = requests.get(GEOCODE_URL, params={"name": location, "count": 1}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        return {}
    r = data["results"][0]
    return {
        "name": r.get("name", location),
        "country": r.get("country", ""),
        "latitude": r["latitude"],
        "longitude": r["longitude"],
    }


def get_weather(latitude: float, longitude: float) -> dict:
    """Fetch current weather for given coordinates."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main_function(location: str = "New York") -> str:
    """Get current weather for a location. Returns a markdown-formatted string."""
    try:
        geo = _geocode(location)
        if not geo:
            return f"Sorry, I couldn't find a location matching **{location}**."

        data = get_weather(geo["latitude"], geo["longitude"])
        current = data.get("current", {})

        temp = current.get("temperature_2m", "N/A")
        feels_like = current.get("apparent_temperature", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        wind = current.get("wind_speed_10m", "N/A")
        code = current.get("weather_code", -1)
        condition = WMO_CODES.get(code, "Unknown")

        place = geo["name"]
        if geo.get("country"):
            place += f", {geo['country']}"

        return (
            f"**Weather in {place}**\n\n"
            f"- **Condition:** {condition}\n"
            f"- **Temperature:** {temp}°C (feels like {feels_like}°C)\n"
            f"- **Humidity:** {humidity}%\n"
            f"- **Wind:** {wind} km/h"
        )
    except Exception as e:
        return f"Error fetching weather: {str(e)}"


TOOL_META = {
    "name": "weather_openmeteo",
    "description": "Get current weather for any location using the free Open-Meteo API. No API key required.",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City or place name, e.g. 'London' or 'Tokyo'",
            },
        },
    },
    "function": main_function,
}

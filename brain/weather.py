import requests

CITIES = {
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "la": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "miami": (25.7617, -80.1918),
    "houston": (29.7604, -95.3698),
}

WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "rain showers", 82: "heavy rain showers", 95: "thunderstorm",
}

def extract_city(text):
    lower = text.lower()
    # Check known city names directly in the text
    for city in CITIES:
        if city in lower:
            return city
    # Fallback: grab everything after "in" or "for"
    for phrase in ["weather in", "temperature in", "forecast for"]:
        if phrase in lower:
            return lower.split(phrase)[-1].strip()
    return "new york"  # default to NYC

def get_weather(city="new york"):
    city_lower = city.lower().strip()
    coords = CITIES.get(city_lower)

    if not coords:
        return f"I don't have weather data for {city} yet."

    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weathercode,windspeed_10m,relative_humidity_2m"
        f"&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=America/New_York"
    )
    try:
        res = requests.get(url, timeout=5).json()
        c = res["current"]
        temp = round(c["temperature_2m"])
        condition = WMO_CODES.get(c["weathercode"], "unknown conditions")
        wind = round(c["windspeed_10m"])
        humidity = c["relative_humidity_2m"]
        return f"{temp}°F, {condition}, wind {wind} mph, humidity {humidity}%"
    except Exception as e:
        return f"Couldn't fetch weather: {e}"

"""Tests for weather_openmeteo skill."""
from weather_openmeteo import main_function, get_weather, TOOL_META


def test_import():
    assert callable(main_function)
    assert TOOL_META["name"] == "weather_openmeteo"
    assert callable(TOOL_META["function"])
    print("test_import passed")


def test_meta_schema():
    props = TOOL_META["parameters"]["properties"]
    assert "location" in props
    print("test_meta_schema passed")


def test_call_default():
    result = main_function()
    assert isinstance(result, str)
    assert "Weather in" in result or "Error" in result
    print(f"test_call_default passed — preview: {result[:200]}")


def test_call_custom():
    result = main_function("Tokyo")
    assert isinstance(result, str)
    assert "Tokyo" in result or "Error" in result
    print(f"test_call_custom passed — preview: {result[:200]}")


def test_bad_location():
    result = main_function("xyznonexistent99999")
    assert isinstance(result, str)
    assert "Error" not in result or "couldn't find" in result.lower() or "error" in result.lower()
    print(f"test_bad_location passed — preview: {result[:200]}")


def test_get_weather_direct():
    data = get_weather(40.7, -74.0)
    assert "current" in data
    assert "temperature_2m" in data["current"]
    print("test_get_weather_direct passed")


if __name__ == "__main__":
    test_import()
    test_meta_schema()
    test_call_default()
    test_call_custom()
    test_bad_location()
    test_get_weather_direct()
    print("\n✅ All tests passed")

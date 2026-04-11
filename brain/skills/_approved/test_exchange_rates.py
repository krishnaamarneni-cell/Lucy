"""Tests for Lucy skill: exchange_rates"""
from exchange_rates import main_function, get_rate, convert_currency, list_rates, TOOL_META


def test_import():
    assert callable(main_function)
    assert TOOL_META["name"] == "exchange_rates"
    assert callable(TOOL_META["function"])
    print("test_import passed")


def test_get_rate():
    result = get_rate("USD", "EUR")
    assert isinstance(result, str)
    assert "USD" in result and "EUR" in result
    print(f"test_get_rate passed: {result}")


def test_convert():
    result = convert_currency("100", "USD", "EUR")
    assert isinstance(result, str)
    assert "100" in result
    print(f"test_convert passed: {result[:200]}")


def test_list_rates():
    result = list_rates("USD")
    assert isinstance(result, str)
    assert "EUR" in result
    print(f"test_list_rates passed: {result[:200]}")


def test_main_function_convert():
    result = main_function(action="convert", amount="50", source="GBP", target="INR")
    assert isinstance(result, str)
    assert "GBP" in result
    print(f"test_main_function_convert passed: {result[:200]}")


def test_main_function_rate():
    result = main_function(action="rate", source="EUR", target="JPY")
    assert isinstance(result, str)
    assert "EUR" in result and "JPY" in result
    print(f"test_main_function_rate passed: {result}")


def test_main_function_list():
    result = main_function(action="list", source="INR")
    assert isinstance(result, str)
    assert "INR" in result
    print(f"test_main_function_list passed: {result[:200]}")


def test_error_handling():
    result = convert_currency("not_a_number", "USD", "EUR")
    assert "Error" in result
    print(f"test_error_handling passed: {result}")


def test_invalid_currency():
    result = get_rate("USD", "ZZZZZ")
    assert "Error" in result
    print(f"test_invalid_currency passed: {result}")


if __name__ == "__main__":
    test_import()
    test_get_rate()
    test_convert()
    test_list_rates()
    test_main_function_convert()
    test_main_function_rate()
    test_main_function_list()
    test_error_handling()
    test_invalid_currency()
    print("\n✅ All tests passed")

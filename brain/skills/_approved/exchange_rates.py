"""Lucy skill: exchange_rates — Currency exchange rates (free, no auth)"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://open.er-api.com/v6/latest"


def get_rate(base: str = "USD", target: str = "EUR") -> str:
    """Get the current exchange rate between two currencies."""
    try:
        base = base.upper().strip()
        target = target.upper().strip()
        resp = requests.get(f"{BASE_URL}/{base}", timeout=10)
        data = resp.json()
        if data.get("result") != "success":
            return f"Error: API returned `{data.get('result', 'unknown')}`"
        rates = data.get("rates", {})
        if target not in rates:
            return f"Error: Unknown currency code `{target}`"
        rate = rates[target]
        return f"**{base} → {target}**: `1 {base} = {rate} {target}`"
    except Exception as e:
        return f"Error: {e}"


def convert_currency(amount: str = "1", source: str = "USD", target: str = "EUR") -> str:
    """Convert an amount from one currency to another."""
    try:
        amt = float(amount)
        source = source.upper().strip()
        target = target.upper().strip()
        resp = requests.get(f"{BASE_URL}/{source}", timeout=10)
        data = resp.json()
        if data.get("result") != "success":
            return f"Error: API returned `{data.get('result', 'unknown')}`"
        rates = data.get("rates", {})
        if target not in rates:
            return f"Error: Unknown currency code `{target}`"
        rate = rates[target]
        converted = round(amt * rate, 2)
        return (
            f"**{amt:,.2f} {source} → {target}**\n\n"
            f"Rate: `1 {source} = {rate} {target}`\n"
            f"Result: **{converted:,.2f} {target}**"
        )
    except ValueError:
        return f"Error: `{amount}` is not a valid number"
    except Exception as e:
        return f"Error: {e}"


def list_rates(base: str = "USD") -> str:
    """List popular exchange rates for a base currency."""
    try:
        base = base.upper().strip()
        resp = requests.get(f"{BASE_URL}/{base}", timeout=10)
        data = resp.json()
        if data.get("result") != "success":
            return f"Error: API returned `{data.get('result', 'unknown')}`"
        rates = data.get("rates", {})
        popular = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "INR", "CHF", "CNY", "BRL"]
        lines = [f"**Exchange rates for {base}**\n"]
        for cur in popular:
            if cur != base and cur in rates:
                lines.append(f"- {cur}: `{rates[cur]}`")
        last_update = data.get("time_last_update_utc", "unknown")
        lines.append(f"\n_Last updated: {last_update}_")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def main_function(action: str = "convert", amount: str = "1", source: str = "USD", target: str = "EUR") -> str:
    """Main entry point — routes to the appropriate sub-function."""
    action = action.lower().strip()
    if action == "rate":
        return get_rate(source, target)
    elif action == "list":
        return list_rates(source)
    else:
        return convert_currency(amount, source, target)


TOOL_META = {
    "name": "exchange_rates",
    "description": "Currency exchange rates (free, no auth). Convert currencies, check rates, and list popular exchange rates.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action to perform: 'convert', 'rate', or 'list'",
                "enum": ["convert", "rate", "list"],
            },
            "amount": {
                "type": "string",
                "description": "Amount to convert (for 'convert' action)",
            },
            "source": {
                "type": "string",
                "description": "Source currency code, e.g. USD",
            },
            "target": {
                "type": "string",
                "description": "Target currency code, e.g. EUR",
            },
        },
    },
    "function": main_function,
}

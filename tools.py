from crewai.tools import tool
from datetime import datetime
import json


@tool("Trip Requirements Parser")
def parse_trip_requirements(user_message: str) -> str:
    """
    Analyzes a user's natural language hotel search request and extracts
    structured trip requirements: destination, check-in, check-out dates,
    number of guests, budget preferences, and any special requirements.

    :param user_message: The user's natural language request
    :return: A structured JSON summary of trip requirements
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return json.dumps({
        "raw_request": user_message,
        "today_date": today,
        "instruction": (
            "Extract: destination city/country, check_in_date (YYYY-MM-DD), "
            "check_out_date (YYYY-MM-DD), num_adults (int), max_budget_per_night (USD int or null), "
            "hotel_preferences (list of strings like 'pool', 'free breakfast', 'city center'), "
            "special_notes (string). "
            "If dates are relative (e.g. 'next weekend'), resolve them against today_date. "
            "Return structured JSON."
        )
    })

from crewai.tools import tool
from typing import Optional


@tool("Kayak Hotel URL Generator")
def kayak_hotels(
    location_query: str,
    check_in_date: str,
    check_out_date: str,
    num_adults: int = 2,
    max_price: Optional[int] = None,
    sort_by: str = "price_a"
) -> str:
    """
    Generates a Kayak URL for hotel searches based on location, dates, and guest count.
    Use this to build the search URL before browsing.

    :param location_query: The Kayak location slug (e.g., 'New-York,New-York-State,United-States-c19762' or 'paris/FR')
    :param check_in_date: Check-in date in 'YYYY-MM-DD' format
    :param check_out_date: Check-out date in 'YYYY-MM-DD' format
    :param num_adults: Number of adults (default 2)
    :param max_price: Optional max price per night in USD
    :param sort_by: Sort order — 'price_a' (cheapest first), 'rank_a' (best match), 'rating_a' (top rated)
    :return: Full Kayak hotel search URL
    """
    base_url = f"https://www.kayak.com/hotels/{location_query}/{check_in_date}/{check_out_date}/{num_adults}adults"
    params = [f"sort={sort_by}"]
    if max_price:
        params.append(f"price={max_price}")
    if params:
        base_url += "?" + "&".join(params)
    return base_url

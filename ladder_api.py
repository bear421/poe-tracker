import requests

# Base API URL
BASE_API_URL = "https://pathofexile2.com/internal-api/content/game-ladder/id/"

def fetch_ladder_data(league):
    """
    Fetches ladder data for a specific league.

    :param league: The name of the league (e.g., "Standard").
    :return: Ladder data as JSON, or None if the request fails.
    """
    api_url = f"{BASE_API_URL}{league}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

def fetch_account_data(account_name, league):
    """
    Fetches experience data for a specific account in a league.

    :param account_name: The account name to search for (e.g., "ClandestineBear#7592").
    :param league: The name of the league (e.g., "Standard").
    :return: Experience value or None if the account is not found.
    """
    ladder_data = fetch_ladder_data(league)
    if not ladder_data:
        return None

    entries = ladder_data.get("context", {}).get("ladder", {}).get("entries", [])
    for entry in entries:
        if entry.get("account", {}).get("name") == account_name:
            return entry.get("character", {}).get("experience")

    return None

# Example usage
if __name__ == "__main__":
    league = "Standard"
    account_name = "ClandestineBear#7592"

    # Fetch account data
    experience = fetch_account_data(account_name, league)
    if experience:
        print(f"Experience for {account_name} in {league}: {experience}")
    else:
        print(f"Account {account_name} not found in {league} league.")

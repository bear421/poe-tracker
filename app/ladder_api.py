import requests
from dataclasses import dataclass
from typing import Optional, List

# Base API URL
BASE_API_URL = "https://pathofexile2.com/internal-api/content/game-ladder/id/"

@dataclass
class TwitchStream:
    name: str
    status: str
    image: str

@dataclass
class TwitchInfo:
    name: str
    stream: Optional[TwitchStream] = None

@dataclass
class Challenges:
    set: str
    completed: int
    max: int

@dataclass
class Account:
    name: str
    challenges: Optional[Challenges]
    twitch: Optional[TwitchInfo] = None

@dataclass
class Character:
    id: str
    name: str
    level: int
    class_name: str  # using class_name since 'class' is a reserved word
    experience: int

@dataclass
class LadderEntry:
    rank: int
    dead: bool
    public: Optional[bool]
    character: Character
    account: Account

def fetch_ladder_data(league:str="Standard"):
    """
    Fetches ladder data for a specific league.

    :param league: The name of the league (e.g., "Standard").
    :return: Ladder data as JSON, or None if the request fails.
    """
    if not league:
        raise ValueError("League is required")

    api_url = f"{BASE_API_URL}{league}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

def fetch_data(account_name:str=None, character_name:str=None, league: str=None) -> Optional[LadderEntry]:
    """
    Fetches experience data for a specific account in a league.

    :param account_name: The account name to search for (e.g., "ClandestineBear#7592").
    :param character_name: The character name to search for.
    :param league: The name of the league (e.g., "Standard").
    :return: LadderEntry object or None if the account/character is not found.
    """
    if not account_name and not character_name:
        return fetch_ladder_data(league)

    ladder_data = fetch_ladder_data(league)
    if not ladder_data:
        return None

    entries = ladder_data.get("context", {}).get("ladder", {}).get("entries", [])
    for entry in entries:
        if account_name and entry.get("account", {}).get("name") == account_name:
            pass
        elif character_name and entry.get("character", {}).get("name") == character_name:
            pass
        else:
            continue
        
        # Convert the raw entry to our dataclass structure
        char_data = entry["character"]
        character = Character(
            id=char_data["id"],
            name=char_data["name"],
            level=char_data["level"],
            class_name=char_data["class"],
            experience=char_data["experience"]
        )

        acc_data = entry["account"]
        challenges = None
        if "challenges" in acc_data and isinstance(acc_data["challenges"], dict):
            challenges = Challenges(
                set=acc_data["challenges"]["set"],
                completed=acc_data["challenges"]["completed"],
                max=acc_data["challenges"]["max"]
            )

        twitch = None
        if "twitch" in acc_data:
            twitch_data = acc_data["twitch"]
            stream = None
            if "stream" in twitch_data:
                stream = TwitchStream(
                    name=twitch_data["stream"]["name"],
                    status=twitch_data["stream"]["status"],
                    image=twitch_data["stream"]["image"]
                )
            twitch = TwitchInfo(name=twitch_data["name"], stream=stream)

        account = Account(
            name=acc_data["name"],
            challenges=challenges,
            twitch=twitch
        )

        return LadderEntry(
            rank=entry["rank"],
            dead=entry["dead"],
            public=entry.get("public"),
            character=character,
            account=account
        )

    return None

# Example usage
if __name__ == "__main__":
    league = "Standard"
    account_name = None
    character_name = "SneakyBear"

    # Fetch account data
    entry = fetch_data(account_name, character_name, league)
    if entry:
        print(f"Found character {entry.character.name}")
        print(f"Level: {entry.character.level}")
        print(f"Experience: {entry.character.experience}")
        print(f"Account: {entry.account.name}")
        if entry.account.twitch:
            print(f"Twitch: {entry.account.twitch.name}")
    else:
        print(f"Account {account_name} not found in {league} league.")

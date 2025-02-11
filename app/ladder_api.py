import requests
from dataclasses import dataclass
from typing import Optional, List
import json
# Base API URL
BASE_API_URL = "https://pathofexile2.com/internal-api/content/game-ladder/id/"

@dataclass
class TwitchStream:
    name: str
    status: str
    image: str

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "image": self.image
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            status=data["status"],
            image=data["image"]
        )

@dataclass
class TwitchInfo:
    name: str
    stream: Optional[TwitchStream] = None

    def to_dict(self):
        return {
            "name": self.name,
            "stream": self.stream.to_dict() if self.stream else None
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            stream=TwitchStream.from_dict(data["stream"]) if data["stream"] else None
        )

@dataclass
class Challenges:
    set: str
    completed: int
    max: int

    def to_dict(self):
        return {
            "set": self.set,
            "completed": self.completed,
            "max": self.max
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            set=data["set"],
            completed=data["completed"],
            max=data["max"]
        )

@dataclass
class Account:
    name: str
    challenges: Optional[Challenges]
    twitch: Optional[TwitchInfo] = None

    def to_dict(self):
        return {
            "name": self.name,
            "challenges": self.challenges.to_dict() if self.challenges else None,
            "twitch": self.twitch.to_dict() if self.twitch else None
        }   

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            challenges=Challenges.from_dict(data["challenges"]) if data["challenges"] else None,
            twitch=TwitchInfo.from_dict(data["twitch"]) if data["twitch"] else None
        )

@dataclass
class Character:
    id: str
    name: str
    level: int
    class_name: str  # using class_name since 'class' is a reserved word
    experience: int

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "class_name": self.class_name,
            "experience": self.experience
        }   

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            name=data["name"],
            level=data["level"],
            class_name=data["class_name"],
            experience=data["experience"]
        )

@dataclass
class LadderEntry:
    rank: int
    dead: bool
    public: Optional[bool]
    character: Character
    account: Account
    prev: Optional['LadderEntry'] = None
    next: Optional['LadderEntry'] = None

    def to_dict(self):
        return {
            "rank": self.rank,
            "dead": self.dead,
            "public": self.public,
            "character": self.character.to_dict(),
            "account": self.account.to_dict(),
            "prev": self.prev.to_dict() if self.prev else None,
            "next": self.next.to_dict() if self.next else None
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            rank=data["rank"],
            dead=data["dead"],
            public=data["public"],
            character=Character.from_dict(data["character"]),
            account=Account.from_dict(data["account"]),
            prev=cls.from_dict(data["prev"]) if data.get("prev") else None,
            next=cls.from_dict(data["next"]) if data.get("next") else None
        )

    @classmethod
    def from_row(cls, data):
        return cls.from_dict(json.loads(data))

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
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"}
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

def fetch_data(account_name:str=None, character_name:str=None, league: str=None) -> Optional[LadderEntry]:
    if not account_name and not character_name:
        raise ValueError("must specify account_name or character_name")

    ladder_data = fetch_ladder_data(league)
    if not ladder_data:
        return None

    entries = ladder_data.get("context", {}).get("ladder", {}).get("entries", [])
    
    for i, entry in enumerate(entries):
        if account_name and entry.get("account", {}).get("name") != account_name:
            continue
        elif character_name and entry.get("character", {}).get("name") != character_name:
            continue
        
        current_entry = mk_ladder_entry(entry)
        if i > 0:
            current_entry.prev = mk_ladder_entry(entries[i - 1])
        if i < len(entries) - 1:
            current_entry.next = mk_ladder_entry(entries[i + 1])
            
        return current_entry

    return None

def mk_ladder_entry(entry) -> LadderEntry:
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

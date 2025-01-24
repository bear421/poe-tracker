from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import re
import uuid
import json

class ModType(Enum):
    ENCHANT = "enchant"
    IMPLICIT = "implicit"
    AFFIX = "affix"
    CRAFTED = "crafted"
    UNKNOWN = "unknown"

@dataclass
class Mod:
    text: str
    type: ModType = ModType.UNKNOWN
    value: Optional[float] = None

    @staticmethod
    def parse(text: str) -> 'Mod':
        """Parse a mod line into a Mod object."""
        # First check for explicit mod types in the text
        if "(enchant)" in text:
            mod_type = ModType.ENCHANT
        elif "(implicit)" in text:
            mod_type = ModType.IMPLICIT
        elif "(crafted)" in text:
            mod_type = ModType.CRAFTED
        else:
            mod_type = ModType.AFFIX

        # Clean up the mod text
        clean_text = re.sub(r"\s*\((enchant|implicit|crafted)\)", "", text)
        
        # Try to extract numeric values
        value = None
        value_match = re.search(r'(-?\d+\.?\d*)', clean_text)
        if value_match:
            value = float(value_match.group(1))

        return Mod(
            text=clean_text,
            type=mod_type,
            value=value
        )

    @staticmethod
    def from_dict(data: Dict) -> 'Mod':
        """Create a Mod instance from a dictionary."""
        return Mod(
            text=data["text"],
            type=ModType.UNKNOWN,  # Since we don't store type in dict
            value=data.get("value")
        )

@dataclass
class Item:
    id: str
    name: str
    base_type: str
    item_class: str
    rarity: str
    item_level: Optional[int] = None
    corrupted: bool = False
    
    # Properties
    properties: Dict[str, str] = field(default_factory=dict)
    
    # Mods
    enchants: List[Mod] = field(default_factory=list)
    implicits: List[Mod] = field(default_factory=list)
    affixes: List[Mod] = field(default_factory=list)

    def tier(self):
        # TODO
        return 1

    def to_dict(self) -> Dict:
        """Convert item to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "base_type": self.base_type,
            "item_class": self.item_class,
            "rarity": self.rarity,
            "item_level": self.item_level,
            "corrupted": self.corrupted,
            "properties": self.properties,
            "enchants": [{"text": mod.text, "value": mod.value} for mod in self.enchants],
            "implicits": [{"text": mod.text, "value": mod.value} for mod in self.implicits],
            "affixes": [{"text": mod.text, "value": mod.value} for mod in self.affixes]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Item':
        """Create an Item instance from a dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            base_type=data["base_type"],
            item_class=data["item_class"],
            rarity=data["rarity"],
            item_level=data["item_level"],
            corrupted=data["corrupted"],
            properties=data["properties"],
            enchants=[Mod.from_dict(m) for m in data["enchants"]],
            implicits=[Mod.from_dict(m) for m in data["implicits"]],
            affixes=[Mod.from_dict(m) for m in data["affixes"]]
        )

    @classmethod
    def from_row(cls, data: Dict) -> 'Item':
        return cls.from_dict(json.loads(data))

def parse_item(item_text: str) -> Optional[Item]:
    """Parse item text into an Item object."""
    sections = [s.strip() for s in item_text.split('--------') if s.strip()]
    if not sections: return None

    # Parse header section
    header = [line.strip() for line in re.split(r'\r?\n', sections[0])]
    item_class_match = re.match(r"Item Class: (.+)", header[0])
    if not item_class_match: return None
    
    item_class = item_class_match.group(1)

    rarity = re.match(r"Rarity: (.+)", header[1]).group(1)
    name = header[2] if len(header) > 3 else None
    base_type = header[3] if len(header) > 3 else header[2]
    
    # Remove tier information from base type if present
    base_type = re.sub(r"\s*\(Tier \d+\)", "", base_type)
    
    # Initialize item
    item = Item(
        id=str(uuid.uuid4()),
        name=name,
        base_type=base_type,
        item_class=item_class,
        rarity=rarity
    )
    
    # Parse remaining sections
    for section in sections[1:]:
        lines = [line.strip() for line in re.split(r'\r?\n', section)]
        
        # Skip description sections
        if any(line.startswith("Can be used") for line in lines):
            continue
            
        # Check for corrupted status
        if section == "Corrupted":
            item.corrupted = True
            continue
            
        # Parse item level
        ilvl_match = re.match(r"Item Level: (\d+)", lines[0])
        if ilvl_match:
            item.item_level = int(ilvl_match.group(1))
            continue
            
        # Parse properties
        if any(":" in line for line in lines):
            for line in lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    # Remove (augmented) from properties
                    value = re.sub(r"\s*\(augmented\)", "", value)
                    item.properties[key.strip()] = value.strip()
            continue
        
        # Parse mods
        for line in lines:
            if not line.strip():
                continue
                
            mod = Mod.parse(line)
            
            if mod.type == ModType.ENCHANT:
                item.enchants.append(mod)
            elif mod.type == ModType.IMPLICIT:
                item.implicits.append(mod)
            else:
                item.affixes.append(mod)
    
    return item

# Example usage
if __name__ == "__main__":
    example_item = """Item Class: Waystones
Rarity: Rare
Terror Course
Waystone (Tier 15)
--------
Waystone Tier: 15
Waystone Drop Chance: +310% (augmented)
--------
Item Level: 79
--------
40% increased Magic Monsters (enchant)
8% increased Pack size (enchant)
Players in Area are 23% Delirious (enchant)
--------
52% increased Magic Pack Size
23% increased Pack size
-15% maximum Player Resistances
Monsters fire 2 additional Projectiles
Monsters have 50% increased Accuracy Rating
--------
Can be used in a Map Device, allowing you to enter a Map. Waystones can only be used once.
--------
Corrupted"""

    item = parse_item(example_item)
    import json
    print(json.dumps(item.to_dict(), indent=2)) 
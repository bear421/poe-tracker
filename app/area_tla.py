from item import Item, Mod, ModType
from dataclasses import dataclass
import re
from typing import Optional

@dataclass
class TI:
    multi: float
    magnitude_range: tuple[int, int]

threat_table = {
    r"Monster Damage Penetrates (\d+)% Elemental Resistances": 
        TI(1.9, (15, 25)),
    r"-(\d+)% maximum Player Resistances": 
        TI(1.8, (10, 15)),
    r"Monsters Fire (\d+) additional Projectiles": 
        TI(1.0, (2, 2)),
    r"Monsters have (\d+)% increased Critical Hit Chance": 
        TI(0.5, (360, 400)),
    r"(\d+)% to Monster Critical Damage Bonus": 
        TI(0.5, (41, 45)),
    r"(\d+)% increased Monster Damage": 
        TI(0.6, (26, 40)),
    r"Players in Area are (\d+)% Delirious": 
        TI(0.5, (1, 100)),
    r"(\d+)% increased Monster Attack Speed": 
        TI(0.25, (21, 35)),
    r"(\d+)% increased Monster Cast Speed": 
        TI(0.25, (21, 35)),
    r"(\d+)% increased Monster Movement Speed": 
        TI(0.05, (21, 35)),
    r"Monsters deal (\d+)% of Damage as Extra Cold": 
        TI(0.25, (26, 40)),
    r"Monsters deal (\d+)% of Damage as Extra Fire": 
        TI(0.25, (26, 40)),
    r"Monsters deal (\d+)% of Damage as Extra Lightning": 
        TI(0.25, (26, 40)),
    r"Monsters have (\d+)% increased Stun Buildup": 
        TI(0.1, (20, 30)),
    r"Monsters have (\d+)% increased Area of Effect": 
        TI(0.1, (50, 50)),
    r"Area has patches of Shocked Ground": 
        TI(0.1, (0, 0)),    
    r"Area has patches of Chilled Ground": 
        TI(0.05, (0, 0)),    
    r"Area has patches of Burning Ground": 
        TI(0.05, (0, 0)),
    r"\+(\d+)% Monster Elemental Resistances": 
        TI(0.05, (40, 50)),
    r"Players are cursed with Enfeeble": 
        TI(0.05, (0, 0)),
    r"Players are cursed with Temporal Chains": 
        TI(0.05, (0, 0)),
    r"Players are cursed with Elemental Weakness": 
        TI(0.05, (0, 0)),
    r"Monsters deal (\d+)% of Damage as Extra Chaos": 
        TI(0, (25, 40))
}

threat_level_hints = [
    (0, "safe"),
    (15, "low"),
    (20, "medium"),
    (30, "dangerous"),
    (50, "deadly"),
    (150, "lethal"),
    (float('inf'), "apocalyptic")
]

def get_threat_indicator(mod: Mod) -> Optional[TI]:
    for pattern, ti in threat_table.items():
        m = re.search(pattern, mod.text, re.IGNORECASE)
        if m:
            return ti
    return None

def get_threat_level(waystone: Item):    
    threat_level_half_mul = 1
    threat_level_half_add = 0
    
    def evaluate_mod(affix: Mod):
        nonlocal threat_level_half_mul, threat_level_half_add
        for pattern, ti in threat_table.items():
            m = re.search(pattern, affix.text, re.IGNORECASE)
            if m:
                delta = (1 + ti.multi) ** 0.6
                threat_level_half_mul *= delta
                val = float(m.group(1)) if m.groups() else 1
                range_lo, range_hi = ti.magnitude_range
                if range_lo == range_hi:
                    range_p = 1
                else:
                    range_p = 1.5 * max(0, min(1, (val - range_lo) / (range_hi - range_lo)))
                threat_level_half_add += delta * range_p

    for mod in waystone.affixes:
        evaluate_mod(mod)

    for mod in waystone.enchants:
        evaluate_mod(mod)

    threat_level = int(round(10 * threat_level_half_mul + threat_level_half_add)) if threat_level_half_mul > 1 else 0
    
    for threshold, hint in threat_level_hints:
        if threat_level <= threshold:
            return threat_level, hint

    return threat_level, "unknown"
    

if __name__ == "__main__":
    def mk_example_item(affixes: list[Mod]):
        return Item(
            name="Terror Course",
            base_type="Waystone",
            item_class="Waystones", 
            rarity="Rare",
            item_level=79,
            affixes=affixes
        )

    threat = get_threat_level(mk_example_item(
        [
            Mod("-15% maximum Player Resistances", ModType.AFFIX),
            Mod("Monsters fire 2 additional Projectiles", ModType.AFFIX),
            Mod("Monster Damage Penetrates 25% Elemental Resistances", ModType.AFFIX),
        ]
    ))

    print(f"Threat level high: {threat}")
    
    threat = get_threat_level(mk_example_item(
        [
            Mod("Monsters have 366% increased Critical Hit Chance", ModType.AFFIX),
            Mod("+42% to Monster Critical Damage Bonus", ModType.AFFIX),
            Mod("Monsters deal 40% of Damage as Extra Fire", ModType.AFFIX),
            Mod("Players are Cursed with Enfeeble", ModType.AFFIX),
            Mod("Monsters have 25% chance to Bleed on Hit", ModType.AFFIX),
        ]
    ))
    print(f"Threat level high (crit + fire): {threat}")

    threat = get_threat_level(mk_example_item(
        [
            Mod("Monster Damage Penetrates 25% Elemental Resistances", ModType.AFFIX),
        ]
    ))
    print(f"Threat level medimum (single rippy): {threat}")

    threat = get_threat_level(mk_example_item(
        [
            Mod("Monsters fire 2 additional Projectiles", ModType.AFFIX),
            Mod("Monsters deal 40% of Damage as Extra Fire", ModType.AFFIX)
        ]
    ))
    print(f"Threat level medimum (lmp + fire): {threat}")

    threat = get_threat_level(mk_example_item(
        [
            Mod("52% increased Magic Pack Size", ModType.AFFIX),
            Mod("25% increased Monster Attack Speed", ModType.AFFIX),
            Mod("25% increased Monster Cast Speed", ModType.AFFIX),
        ]
    ))
    print(f"Threat level fleet: {threat}")

    threat = get_threat_level(mk_example_item(
        [
            Mod("Monsters deal 40% of Damage as Extra Cold", ModType.AFFIX),
            Mod("Monsters deal 40% of Damage as Extra Fire", ModType.AFFIX)
        ]
    ))
    print(f"Threat level as extra cold/fire: {threat}")

    threat = get_threat_level(mk_example_item(
        [
            Mod("Monsters deal 25% of Damage as Extra Cold", ModType.AFFIX),
        ]
    ))
    print(f"Threat level as extra cold: {threat}")

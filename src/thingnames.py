from typing import Optional

# IWADs do not actually contain names, they have to be provided externally.

COMMON_THING_NAMES: dict[int, str] = {
    1: "Player 1 Start",
    2: "Player 2 Start",
    3: "Player 3 Start",
    4: "Player 4 Start",
    11: "Deathmatch Start",
    14: "Teleport Landing",
    3004: "Zombieman",
    9: "Shotgun Guy",
    65: "Chaingunner",
    3001: "Imp",
    3002: "Demon",
    58: "Spectre",
    3006: "Lost Soul",
    3005: "Cacodemon",
    69: "Hell Knight",
    3003: "Baron of Hell",
    68: "Arachnotron",
    71: "Pain Elemental",
    66: "Revenant",
    67: "Mancubus",
    64: "Arch-vile",
    7: "Spider Mastermind",
    16: "Cyberdemon",
    84: "Wolfenstein SS",
    88: "Boss Brain",
    89: "Boss Shooter",
    87: "Spawn Spot",
    2001: "Shotgun",
    2002: "Chaingun",
    2003: "Rocket Launcher",
    2004: "Plasma Gun",
    2005: "Chainsaw",
    2006: "BFG9000",
    2007: "Ammo Clip",
    2008: "Shotgun Shells",
    2010: "Rocket",
    2047: "Energy Cell",
    2048: "Box of Ammo",
    2049: "Box of Shells",
    2046: "Box of Rockets",
    17: "Cell Pack",
    2011: "Stimpack",
    2012: "Medikit",
    2014: "Health Bonus",
    2015: "Armor Bonus",
    2018: "Green Armor",
    2019: "Blue Armor",
    5: "Blue Keycard",
    6: "Yellow Keycard",
    13: "Red Keycard",
    38: "Red Skull Key",
    39: "Yellow Skull Key",
    40: "Blue Skull Key",
    8: "Backpack",
    2013: "Soulsphere",
    2022: "Invulnerability",
    2023: "Berserk",
    2024: "Invisibility",
    2025: "Radiation Suit",
    2026: "Computer Map",
    2045: "Light Amplification Visor",
}

DOOM1_ONLY_NAMES: dict[int, str] = {
    72: "Commander Keen",
}

DOOM2_ONLY_NAMES: dict[int, str] = {
    64: "Arch-vile",
    65: "Chaingunner",
    66: "Revenant",
    67: "Mancubus",
    68: "Arachnotron",
    69: "Hell Knight",
    71: "Pain Elemental",
    84: "Wolfenstein SS",
    88: "Boss Brain",
    89: "Boss Shooter",
}


def thing_name_for(game_profile: str | None, thing_id: int) -> Optional[str]:
    if game_profile == "doom1":
        if thing_id in DOOM1_ONLY_NAMES:
            return DOOM1_ONLY_NAMES[thing_id]
        if thing_id in {64, 65, 66, 67, 68, 69, 71, 84, 88, 89}:
            return None

    if game_profile == "doom2" and thing_id in DOOM2_ONLY_NAMES:
        return DOOM2_ONLY_NAMES[thing_id]

    return COMMON_THING_NAMES.get(thing_id)

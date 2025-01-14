import bisect

# Experience table mapping levels to total XP required (lower bounds)
experience_table = [
    0, 525, 1760, 3781, 7184, 12186, 19324, 29377, 43181, 61693, 85990,
    117506, 157384, 207736, 269997, 346462, 439268, 550344, 681662, 835216,
    1013048, 1220421, 1461447, 1740261, 2061612, 2430865, 2854052, 3337945,
    3890110, 4518943, 5233726, 6044727, 6963260, 8001762, 9173876, 10494990,
    11988903, 13681215, 15591260, 17740199, 20151112, 22849128, 25861603,
    29218253, 32951323, 37095773, 41689401, 46772984, 52390426, 58588914,
    65419052, 72935044, 81194925, 90260770, 101197914, 112999703, 125876627,
    139911841, 155193672, 171815566, 189876498, 209481841, 230743635,
    253780693, 278718891, 305691277, 334838273, 366308802, 400258449,
    436850599, 476256603, 518656939, 564241429, 613209429, 665770051,
    722142340, 782555498, 847249123, 916473400, 990489362, 1069595597,
    1154546988, 1245225522, 1341995050, 1445230845
]

# Total levels available
max_level = len(experience_table)

def get_level_from_xp(xp):
    """
    Get the character level for a given experience value using binary search.

    :param xp: The experience value to search for.
    :return: The level corresponding to the given experience.
    """
    index = bisect.bisect_right(experience_table, xp) - 1
    return index + 1 if 0 <= index < max_level else None

def get_xp_range_for_level(level):
    """
    Get the XP range (lower and upper bounds) for a given level.

    :param level: The level to retrieve the XP range for.
    :return: A tuple (lower_bound, upper_bound) or None if the level is invalid.
    """
    if 1 <= level < max_level:
        return experience_table[level - 1], experience_table[level]
    elif level == max_level:
        return experience_table[level - 1], float('inf')
    return None

# Example Usage
if __name__ == "__main__":
    # Example XP queries
    xp_value = 3969433254  # Example XP for level 99
    level = get_level_from_xp(xp_value)
    print(f"XP {xp_value} corresponds to Level: {level}")

    # Example Level queries
    level_query = 99
    xp_range = get_xp_range_for_level(level_query)
    print(f"Level {level_query} has XP range: {xp_range}")

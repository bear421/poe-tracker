import bisect

# Experience table mapping levels to total XP required (lower bounds)
experience_table = [
    0, 525, 1760, 3781, 7184, 12186, 19324, 29377, 43181, 61693, 
	85990, 117506, 157384, 207736, 269997, 346462, 439268, 551295, 685171, 843709, 
	1030734, 1249629, 1504995, 1800847, 2142652, 2535122, 2984677, 3496798, 4080655, 4742836, 
	5490247, 6334393, 7283446, 8384398, 9541110, 10874351, 12361842, 14018289, 15859432, 17905634, 
	20171471, 22679999, 25456123, 28517857, 31897771, 35621447, 39721017, 44225461, 49176560, 54607467, 
	60565335, 67094245, 74247659, 82075627, 90631041, 99984974, 110197515, 121340161, 133497202, 146749362, 
	161191120, 176922628, 194049893, 212684946, 232956711, 255001620, 278952403, 304972236, 333233648, 363906163, 
	397194041, 433312945, 472476370, 514937180, 560961898, 610815862, 664824416, 723298169, 786612664, 855129128, 
	929261318, 1009443795, 1096169525, 1189918242, 1291270350, 1400795257, 1519130326, 1646943474, 1784977296, 1934009687, 
	2094900291, 2268549086, 2455921256, 2658074992, 2876116901, 3111280300, 3364828162, 3638186694, 3932818530, 4250334444
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
    if level < 1 or level > max_level:
        raise ValueError(f"Level {level} is out of bounds, must be between 1 and {max_level}")
    lo = experience_table[level - 1]
    if 1 <= level < max_level:
        return lo, experience_table[level]
    elif level == max_level:
        return lo, lo

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

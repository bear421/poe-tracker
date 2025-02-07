
def format_number(num):
    if isinstance(num, str):
        num = int(num)
    
    suffixes = [(1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")]
    for divisor, suffix in suffixes:
        if abs(num) >= divisor:
            value = num / divisor
            # Include decimal only if the number is less than 10
            return f"{value:.1f}{suffix}".rstrip('0').rstrip('.') if value < 10 else f"{int(value)}{suffix}"
    
    return str(num)


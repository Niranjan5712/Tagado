from __future__ import annotations


def paise_to_inr(paise: int) -> float:
    return round(paise / 100.0, 2)


def format_inr(paise: int, *, show_paise: bool = True) -> str:
    amount = paise_to_inr(paise)
    # Indian grouping for display in summaries and emails
    negative = amount < 0
    value = abs(amount)
    whole, frac = f"{value:.2f}".split(".")
    if len(whole) <= 3:
        grouped = whole
    else:
        grouped = whole[-3:]
        rest = whole[:-3]
        parts: list[str] = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        grouped = ",".join(reversed(parts)) + "," + grouped
    prefix = "-" if negative else ""
    if not show_paise and frac == "00":
        return f"{prefix}₹{grouped}"
    return f"{prefix}₹{grouped}.{frac}"


def format_inr_display(paise: int) -> str:
    return format_inr(paise, show_paise=False)

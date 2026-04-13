from typing import List
from scrapers.base import Listing

MAX_PRICE = 2400
MIN_BEDROOMS = 2

# 4-cijferige postcodes die BINNEN de A10-ring vallen
# Gebaseerd op Amsterdam postcodekaart
A10_RING_POSTCODES = set(range(1011, 1020))   # Centrum
A10_RING_POSTCODES |= set(range(1051, 1060))  # Oud-West / Westerpark
A10_RING_POSTCODES |= set(range(1052, 1060))
A10_RING_POSTCODES |= set(range(1013, 1016))  # Jordaan
A10_RING_POSTCODES |= set(range(1054, 1059))  # Baarsjes / Oud-West
A10_RING_POSTCODES |= set(range(1071, 1080))  # De Pijp / Oud-Zuid
A10_RING_POSTCODES |= set(range(1072, 1080))
A10_RING_POSTCODES |= set(range(1091, 1100))  # Oost / Watergraafsmeer
A10_RING_POSTCODES |= set(range(1092, 1100))
A10_RING_POSTCODES |= {1021, 1022, 1023, 1024, 1025, 1026, 1031, 1032, 1033}  # Noord (IJ-zone)
A10_RING_POSTCODES |= set(range(1034, 1037))
A10_RING_POSTCODES |= set(range(1011, 1020))
A10_RING_POSTCODES |= set(range(1016, 1020))  # Grachtengordel
A10_RING_POSTCODES |= {1055, 1056, 1057, 1058}  # Bos en Lommer / De Baarsjes
A10_RING_POSTCODES |= {1013, 1014, 1015}  # Jordaan / Haarlemmerbuurt

# Alle Amsterdam postcodes 1011-1099 meerekenen als uitgangspunt,
# dan specifieke uitzonderingen eruit
ALL_AMSTERDAM = set(range(1011, 1100))

# Postcodes BUITEN de A10-ring of in Zuidoost — altijd uitsluiten
EXCLUDED_POSTCODES = set()
EXCLUDED_POSTCODES |= set(range(1101, 1109))  # Zuidoost / Bijlmer
EXCLUDED_POSTCODES |= set(range(1060, 1070))  # Nieuw-West buiten ring
EXCLUDED_POSTCODES |= {1082, 1083, 1084, 1085, 1086}  # Buitenveldert / Zuidas
EXCLUDED_POSTCODES |= set(range(1110, 1200))  # Buiten Amsterdam

# Wijknamen die altijd worden uitgesloten
EXCLUDED_NEIGHBORHOODS = {
    "zuidoost", "bijlmer", "gaasperdam", "driemond", "amsterdam zuidoost",
    "bullewijk", "holendrecht", "venserpolder",
}


def is_within_a10_ring(postcode: str) -> bool:
    """Geeft True als postcode binnen de A10-ring valt (excl. Zuidoost)."""
    if not postcode:
        return True  # Onbekend: niet weggooien op basis van ontbrekend postcode
    pc4_str = postcode.strip()[:4]
    if not pc4_str.isdigit():
        return True
    pc4 = int(pc4_str)
    if pc4 in EXCLUDED_POSTCODES:
        return False
    # Accepteer alle Amsterdam postcodes die niet expliciet zijn uitgesloten
    return 1010 <= pc4 <= 1099


def is_excluded_neighborhood(neighborhood: str) -> bool:
    return neighborhood.lower().strip() in EXCLUDED_NEIGHBORHOODS


def apply_filters(listings: List[Listing]) -> List[Listing]:
    result = []
    for l in listings:
        if l.price is not None and l.price > MAX_PRICE:
            continue
        if l.bedrooms is not None and l.bedrooms < MIN_BEDROOMS:
            continue
        if is_excluded_neighborhood(l.neighborhood):
            continue
        if not is_within_a10_ring(l.postcode):
            continue
        result.append(l)
    return result

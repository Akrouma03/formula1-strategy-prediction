"""Explicit identities for the 2014–2016 archive; no fuzzy matching.

Original source names stay in DriverId. Unknown names receive a visibly unmapped
ID so they can be audited, never silently assigned to a known driver.
"""

import re
import unicodedata

DRIVERS = {
    "alonso": ("Fernando Alonso", ["alonso"]),
    "bianchi": ("Jules Bianchi", ["jules_bianchi"]),
    "bottas": ("Valtteri Bottas", ["bottas"]),
    "button": ("Jenson Button", ["button"]),
    "chilton": ("Max Chilton", ["chilton"]),
    "ericsson": ("Marcus Ericsson", ["ericsson", "ericssson"]),
    "grosjean": ("Romain Grosjean", ["grosjean"]),
    "gutierrez": ("Esteban Gutierrez", []),
    "hamilton": ("Lewis Hamilton", ["hamilton"]),
    "hulkenberg": ("Nico Hulkenberg", []),
    "kobayashi": ("Kamui Kobayashi", ["kobayashi"]),
    "kvyat": ("Daniil Kvyat", ["kvyat"]),
    "lotterer": ("Andre Lotterer", []),
    "magnussen": ("Kevin Magnussen", ["kevin_magnussen", "Kevin Magnessun"]),
    "maldonado": ("Pastor Maldonado", ["maldonado", "Pastor Maldonando"]),
    "massa": ("Felipe Massa", ["massa"]),
    "merhi": ("Roberto Merhi", []),
    "nasr": ("Felipe Nasr", ["Filipe Nasr"]),
    "ocon": ("Esteban Ocon", []),
    "palmer": ("Jolyon Palmer", []),
    "perez": ("Sergio Perez", []),
    "raikkonen": ("Kimi Raikkonen", []),
    "ricciardo": ("Daniel Ricciardo", ["ricciardo"]),
    "rosberg": ("Nico Rosberg", ["rosberg"]),
    "rossi": ("Alexander Rossi", []),
    "sainz": ("Carlos Sainz", ["Carlos Sainz Jnr"]),
    "stevens": ("Will Stevens", []),
    "sutil": ("Adrian Sutil", ["sutil"]),
    "vandoorne": ("Stoffel Vandoorne", []),
    "vergne": ("Jean-Eric Vergne", []),
    "verstappen": ("Max Verstappen", []),
    "vettel": ("Sebastian Vettel", ["vettel"]),
    "wehrlein": ("Pascal Wehrlein", []),
    "haryanto": ("Rio Haryanto", []),
}


def name_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\s_-]+", " ", text.strip()).casefold()


ALIASES = {
    name_key(alias): identity
    for identity, (name, aliases) in DRIVERS.items()
    for alias in [identity, name, *aliases]
}


def driver_id(value: str) -> str:
    key = name_key(value)
    if not key:
        raise ValueError("Driver names cannot be blank.")
    return ALIASES.get(key, "unmapped:" + key)


def driver_name(identity: str, source_name: str) -> str:
    return DRIVERS[identity][0] if identity in DRIVERS else source_name

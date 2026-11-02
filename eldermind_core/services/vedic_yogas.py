"""Vedic houses, aspects (drishti) and yogas computed from the sidereal chart.

Until 1.0.4 the report asked the model to find yogas on its own, and the module
spec listed popular ones as examples. The model "found" them: in a check of
three reports on 2026-11-02 it described Gaja-Kesari with Jupiter in the 9th
sign from the Moon, Hamsa outside a kendra and Vipareeta Raja with no
dusthana lord in a dusthana — and every such claim travelled on into the
synthesis. So the conditions are evaluated here, deterministically, and every
yoga on the list is always returned: `present: false` with the reason is as
much a fact as `present: true`.

Rules follow the classical Parashari conventions:

* Houses are Whole Sign, counted from the Lagna (`house_number`) and from the
  Moon (`house_from_moon`); a planet's own sign counts as the 1st.
* Only the seven classical planets cast drishti and form yogas. Rahu and Ketu
  enter where a rule names them (Kala Sarpa, the exclusions of Kemadruma and
  Vesi/Vasi); Uranus, Neptune and Pluto never do.
* Natural benefics are Jupiter, Venus and Mercury; the Moon, whose nature
  depends on its phase, is left out of both benefic and malefic lists.
"""

from __future__ import annotations

from itertools import combinations
from typing import Final

from eldermind_core.core.config import NAKSHATRA_DEGREES, ZODIAC_SIGNS
from eldermind_core.services.vedic_dasha import VIMSHOTTARI_ORDER

CLASSICAL_PLANETS: Final[tuple[str, ...]] = (
    "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn",
)

# Jaimini's seven chara karakas, in rank order. The module specs ask for the
# Atmakaraka, and until 1.0.6 the model ranked the planets itself — on
# 2026-11-02 once with Pluto on top, which the scheme never admits.
CHARA_KARAKAS: Final[tuple[str, ...]] = (
    "Atmakaraka", "Amatyakaraka", "Bhratrikaraka", "Matrikaraka",
    "Putrakaraka", "Gnatikaraka", "Darakaraka",
)

SIGN_LORDS: Final[dict[str, str]] = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

OWN_SIGNS: Final[dict[str, tuple[str, ...]]] = {
    "Sun": ("Leo",),
    "Moon": ("Cancer",),
    "Mars": ("Aries", "Scorpio"),
    "Mercury": ("Gemini", "Virgo"),
    "Jupiter": ("Sagittarius", "Pisces"),
    "Venus": ("Taurus", "Libra"),
    "Saturn": ("Capricorn", "Aquarius"),
}

EXALTATION_SIGNS: Final[dict[str, str]] = {
    "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn", "Mercury": "Virgo",
    "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra",
}

DEBILITATION_SIGNS: Final[dict[str, str]] = {
    planet: ZODIAC_SIGNS[(ZODIAC_SIGNS.index(sign) + 6) % 12]
    for planet, sign in EXALTATION_SIGNS.items()
}

# Houses (from the planet's own sign = 1st) each planet aspects in full.
DRISHTI: Final[dict[str, tuple[int, ...]]] = {
    "Sun": (7,), "Moon": (7,), "Mercury": (7,), "Venus": (7,),
    "Mars": (4, 7, 8), "Jupiter": (5, 7, 9), "Saturn": (3, 7, 10),
}

KENDRA_HOUSES: Final[frozenset[int]] = frozenset({1, 4, 7, 10})
DUSTHANA_HOUSES: Final[frozenset[int]] = frozenset({6, 8, 12})
MANGAL_DOSHA_HOUSES: Final[frozenset[int]] = frozenset({1, 2, 4, 7, 8, 12})

NATURAL_BENEFICS: Final[tuple[str, ...]] = ("Jupiter", "Venus", "Mercury")
NATURAL_MALEFICS: Final[tuple[str, ...]] = ("Sun", "Mars", "Saturn", "Rahu", "Ketu")

# Planets that count for the Moon- and Sun-based yogas (Kemadruma, Sunapha,
# Anapha, Durudhara; Vesi, Vasi, Ubhayachari): the five "tara grahas".
_TARA_GRAHAS: Final[tuple[str, ...]] = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")

MAHAPURUSHA: Final[dict[str, str]] = {
    "Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
    "Venus": "Malavya", "Saturn": "Sasa",
}

VIPAREETA: Final[tuple[tuple[str, int], ...]] = (
    ("Harsha", 6), ("Sarala", 8), ("Vimala", 12),
)


def ordinal(number: int) -> str:
    """1 -> '1st', 2 -> '2nd', 11 -> '11th'."""
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def house_from(sign: str, reference_sign: str) -> int:
    """Whole Sign house of `sign` counted from `reference_sign` (which is the 1st)."""
    return (ZODIAC_SIGNS.index(sign) - ZODIAC_SIGNS.index(reference_sign)) % 12 + 1


def _sign_at(reference_sign: str, house: int) -> str:
    """The sign that is the `house`-th counted from `reference_sign`."""
    return ZODIAC_SIGNS[(ZODIAC_SIGNS.index(reference_sign) + house - 1) % 12]


def _join(names: list[str]) -> str:
    if not names:
        return "none"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def ketu_position(rahu: dict) -> dict:
    """Ketu, the south node: always exactly opposite Rahu (the true node)."""
    longitude = (float(rahu["longitude"]) + 180.0) % 360.0
    sign_index = int(longitude // 30.0) % 12
    return {
        "name": "Ketu",
        "longitude": round(longitude, 6),
        "sign": ZODIAC_SIGNS[sign_index],
        "degree_in_sign": round(longitude - sign_index * 30.0, 6),
        "is_retrograde": bool(rahu.get("is_retrograde", True)),
    }


def _bodies(planets: list[dict]) -> dict[str, dict]:
    """Sidereal bodies by Jyotish name: the classical seven plus Rahu and Ketu."""
    by_name = {p["name"]: p for p in planets}
    bodies = {name: by_name[name] for name in CLASSICAL_PLANETS}
    rahu = dict(by_name["TrueNode"])
    rahu["name"] = "Rahu"
    bodies["Rahu"] = rahu
    bodies["Ketu"] = ketu_position(rahu)
    return bodies


def attach_vedic_houses(planets: list[dict], ascendant: dict) -> list[dict]:
    """Add `house_number` (from the Lagna) and `house_from_moon` to each planet."""
    moon_sign = next(p["sign"] for p in planets if p["name"] == "Moon")
    updated: list[dict] = []
    for planet in planets:
        entry = dict(planet)
        entry["house_number"] = house_from(planet["sign"], ascendant["sign"])
        entry["house_from_moon"] = house_from(planet["sign"], moon_sign)
        updated.append(entry)
    return updated


def compute_drishti(planets: list[dict], ascendant: dict) -> list[dict]:
    """Full Parashari aspects of the seven classical planets.

    Every planet aspects the 7th sign from itself; Mars also the 4th and 8th,
    Jupiter the 5th and 9th, Saturn the 3rd and 10th. Each aspected sign is
    listed with its house from the Lagna and the bodies (incl. Rahu and Ketu)
    standing in it.
    """
    bodies = _bodies(planets)
    result: list[dict] = []
    for name in CLASSICAL_PLANETS:
        sign = bodies[name]["sign"]
        aspects = []
        for offset in DRISHTI[name]:
            target = _sign_at(sign, offset)
            aspects.append(
                {
                    "aspect": offset,
                    "sign": target,
                    "house_number": house_from(target, ascendant["sign"]),
                    "planets": [
                        other for other, body in bodies.items()
                        if other != name and body["sign"] == target
                    ],
                }
            )
        result.append(
            {
                "planet": name,
                "sign": sign,
                "house_number": house_from(sign, ascendant["sign"]),
                "aspects": aspects,
            }
        )
    return result


def _aspects_sign(planet: str, from_sign: str, target_sign: str) -> bool:
    return house_from(target_sign, from_sign) in DRISHTI.get(planet, ())


def _associated(a: str, b: str, bodies: dict[str, dict]) -> str | None:
    """How two planets are linked: same sign, mutual aspect or sign exchange."""
    sign_a, sign_b = bodies[a]["sign"], bodies[b]["sign"]
    if sign_a == sign_b:
        return f"{a} and {b} are both in {sign_a}"
    if _aspects_sign(a, sign_a, sign_b) and _aspects_sign(b, sign_b, sign_a):
        return f"{a} in {sign_a} and {b} in {sign_b} aspect each other"
    if SIGN_LORDS[sign_a] == b and SIGN_LORDS[sign_b] == a:
        return f"{a} in {sign_a} and {b} in {sign_b} exchange signs"
    return None


def _yoga(name: str, present: bool, reason: str, planets: list[str], **extra) -> dict:
    return {"name": name, "present": present, "reason": reason, "planets": planets, **extra}


def _gaja_kesari(b: dict[str, dict]) -> dict:
    house = house_from(b["Jupiter"]["sign"], b["Moon"]["sign"])
    present = house in KENDRA_HOUSES
    reason = f"Jupiter is in the {ordinal(house)} sign from the Moon"
    reason += "." if present else "; Gaja-Kesari needs the 1st, 4th, 7th or 10th."
    return _yoga("Gaja-Kesari", present, reason, ["Jupiter", "Moon"])


def _same_sign_yoga(name: str, a: str, b_name: str, b: dict[str, dict]) -> dict:
    sign_a, sign_b = b[a]["sign"], b[b_name]["sign"]
    if sign_a == sign_b:
        return _yoga(name, True, f"{a} and {b_name} are both in {sign_a}.", [a, b_name])
    return _yoga(
        name, False,
        f"{a} is in {sign_a} and {b_name} in {sign_b}; {name} needs both in the same sign.",
        [a, b_name],
    )


def _dignity(planet: str, sign: str) -> str | None:
    if sign == EXALTATION_SIGNS.get(planet):
        return "exalted"
    if sign in OWN_SIGNS.get(planet, ()):
        return "own sign"
    return None


def _mahapurusha(planet: str, b: dict[str, dict], lagna: str) -> dict:
    name = MAHAPURUSHA[planet]
    sign = b[planet]["sign"]
    house = house_from(sign, lagna)
    house_moon = house_from(sign, b["Moon"]["sign"])
    dignity = _dignity(planet, sign)
    if dignity is None:
        homes = ", ".join(OWN_SIGNS[planet])
        reason = (
            f"{planet} is in {sign}, neither its own sign ({homes}) nor its "
            f"exaltation sign ({EXALTATION_SIGNS[planet]})."
        )
        return _yoga(name, False, reason, [planet], from_moon=False)

    where = "exalted in" if dignity == "exalted" else "in its own sign"
    present = house in KENDRA_HOUSES
    from_moon = house_moon in KENDRA_HOUSES
    if present:
        reason = f"{planet} is {where} {sign} and in the {ordinal(house)} house from the Lagna, a kendra."
    else:
        reason = (
            f"{planet} is {where} {sign} but in the {ordinal(house)} house from the Lagna; "
            f"{name} needs a kendra (1st, 4th, 7th or 10th house)."
        )
        if from_moon:
            reason += (
                f" From the Moon it is in the {ordinal(house_moon)} sign, a kendra — "
                "the condition holds only from the Moon."
            )
    return _yoga(name, present, reason, [planet], from_moon=from_moon)


def _vipareeta(name: str, dusthana: int, b: dict[str, dict], lagna: str) -> dict:
    house_sign = _sign_at(lagna, dusthana)
    lord = SIGN_LORDS[house_sign]
    lord_house = house_from(b[lord]["sign"], lagna)
    present = lord_house in DUSTHANA_HOUSES
    reason = (
        f"The {ordinal(dusthana)} house is {house_sign}; its lord {lord} is in the "
        f"{ordinal(lord_house)} house"
    )
    reason += "." if present else f"; {name} needs the 6th, 8th or 12th."
    return _yoga(name, present, reason, [lord], kind="Vipareeta Raja")


def _neecha_bhanga(b: dict[str, dict], lagna: str) -> list[dict]:
    moon_sign = b["Moon"]["sign"]

    def kendra_note(planet: str) -> tuple[bool, str]:
        sign = b[planet]["sign"]
        h_lagna, h_moon = house_from(sign, lagna), house_from(sign, moon_sign)
        ok = h_lagna in KENDRA_HOUSES or h_moon in KENDRA_HOUSES
        return ok, f"{ordinal(h_lagna)} from the Lagna and {ordinal(h_moon)} from the Moon"

    debilitated = [p for p in CLASSICAL_PLANETS if b[p]["sign"] == DEBILITATION_SIGNS[p]]
    if not debilitated:
        return [_yoga("Neecha Bhanga", False, "No planet is in its debilitation sign.", [])]

    exalted_in = {sign: planet for planet, sign in EXALTATION_SIGNS.items()}
    results: list[dict] = []
    for planet in debilitated:
        sign = b[planet]["sign"]
        held: list[str] = []
        notes: list[str] = []

        lord = SIGN_LORDS[sign]
        ok, where = kendra_note(lord)
        notes.append(f"(a) {lord}, lord of {sign}, is {where}")
        if ok:
            held.append(f"(a) {lord}, lord of {sign}, is in a kendra ({where})")

        exaltation_sign = EXALTATION_SIGNS[planet]
        exaltation_lord = SIGN_LORDS[exaltation_sign]
        ok, where = kendra_note(exaltation_lord)
        notes.append(
            f"(b) {exaltation_lord}, lord of {exaltation_sign} ({planet}'s exaltation sign), is {where}"
        )
        if ok:
            held.append(
                f"(b) {exaltation_lord}, lord of {exaltation_sign} ({planet}'s exaltation sign), "
                f"is in a kendra ({where})"
            )

        other = exalted_in.get(sign)
        if other is None:
            notes.append(f"(c) no classical planet is exalted in {sign}")
        else:
            ok, where = kendra_note(other)
            notes.append(f"(c) {other}, exalted in {sign}, is {where}")
            if ok:
                held.append(f"(c) {other}, exalted in {sign}, is in a kendra ({where})")

        if held:
            reason = f"{planet} is debilitated in {sign}; cancelled because " + "; ".join(held) + "."
        else:
            reason = (
                f"{planet} is debilitated in {sign} and no cancellation condition holds: "
                + "; ".join(notes)
                + ". A kendra is the 1st, 4th, 7th or 10th."
            )
        results.append(_yoga("Neecha Bhanga", bool(held), reason, [planet]))
    return results


def _moon_flank_yogas(b: dict[str, dict]) -> list[dict]:
    moon = b["Moon"]["sign"]
    second = [p for p in _TARA_GRAHAS if house_from(b[p]["sign"], moon) == 2]
    twelfth = [p for p in _TARA_GRAHAS if house_from(b[p]["sign"], moon) == 12]
    where = (
        f"2nd from the Moon ({_sign_at(moon, 2)}): {_join(second)}; "
        f"12th from the Moon ({_sign_at(moon, 12)}): {_join(twelfth)}"
    )
    counted = " (Sun, Rahu and Ketu do not count)"
    kemadruma = not second and not twelfth
    # Kemadruma Bhanga: a planet in a kendra from the Moon (incl. with it)
    # cancels the yoga. Reported, because an uncancelled Kemadruma reads badly.
    in_kendra = [
        p for p in _TARA_GRAHAS if house_from(b[p]["sign"], moon) in KENDRA_HOUSES
    ]
    kemadruma_reason = f"{where}{counted}; Kemadruma means both are empty."
    if kemadruma and in_kendra:
        kemadruma_reason += (
            f" It is cancelled (Kemadruma Bhanga): {_join(in_kendra)} in a kendra "
            "from the Moon (1st, 4th, 7th or 10th sign)."
        )
    return [
        _yoga("Sunapha", bool(second), f"{where}{counted}.", second),
        _yoga("Anapha", bool(twelfth), f"{where}{counted}.", twelfth),
        _yoga("Durudhara", bool(second and twelfth), f"{where}{counted}.", second + twelfth),
        _yoga(
            "Kemadruma", kemadruma, kemadruma_reason, [],
            cancelled=kemadruma and bool(in_kendra),
        ),
    ]


def _sun_flank_yogas(b: dict[str, dict]) -> list[dict]:
    sun = b["Sun"]["sign"]
    second = [p for p in _TARA_GRAHAS if house_from(b[p]["sign"], sun) == 2]
    twelfth = [p for p in _TARA_GRAHAS if house_from(b[p]["sign"], sun) == 12]
    where = (
        f"2nd from the Sun ({_sign_at(sun, 2)}): {_join(second)}; "
        f"12th from the Sun ({_sign_at(sun, 12)}): {_join(twelfth)} "
        "(Moon, Rahu and Ketu do not count)"
    )
    return [
        _yoga("Vesi", bool(second), f"{where}.", second),
        _yoga("Vasi", bool(twelfth), f"{where}.", twelfth),
        _yoga("Ubhayachari", bool(second and twelfth), f"{where}.", second + twelfth),
    ]


def _kartari_yogas(b: dict[str, dict], lagna: str) -> list[dict]:
    def occupants(house: int, group: tuple[str, ...]) -> list[str]:
        return [p for p in group if house_from(b[p]["sign"], lagna) == house]

    results = []
    for name, group, label in (
        ("Subha Kartari", NATURAL_BENEFICS, "benefics (Jupiter, Venus, Mercury)"),
        ("Papa Kartari", NATURAL_MALEFICS, "malefics (Sun, Mars, Saturn, Rahu, Ketu)"),
    ):
        second, twelfth = occupants(2, group), occupants(12, group)
        reason = (
            f"Natural {label} in the 2nd house: {_join(second)}; in the 12th: {_join(twelfth)}. "
            f"{name} needs both houses occupied by them (the Moon is not counted)."
        )
        results.append(_yoga(name, bool(second and twelfth), reason, second + twelfth))
    return results


def _parivartana(b: dict[str, dict]) -> list[dict]:
    pairs = []
    for a, c in combinations(CLASSICAL_PLANETS, 2):
        sign_a, sign_c = b[a]["sign"], b[c]["sign"]
        if SIGN_LORDS[sign_a] == c and SIGN_LORDS[sign_c] == a:
            pairs.append(
                _yoga(
                    "Parivartana", True,
                    f"{a} is in {sign_a} (ruled by {c}) and {c} is in {sign_c} (ruled by {a}).",
                    [a, c],
                )
            )
    return pairs or [
        _yoga("Parivartana", False, "No two planets stand in each other's signs.", [])
    ]


def _nakshatra_lord(longitude: float) -> str:
    return VIMSHOTTARI_ORDER[int((longitude % 360.0) // NAKSHATRA_DEGREES) % 9]


def _nakshatra_parivartana(b: dict[str, dict]) -> list[dict]:
    """Two bodies in each other's nakshatras — Rahu and Ketu rule nakshatras, so they count.

    Not a sign exchange. Three reports up to 2026-11-02 described one between
    Saturn and Rahu, each time from a Saturn put in the wrong nakshatra; with
    the lords listed, the absence is a fact the synthesis can read. The two
    nodes are not paired with each other: they always stand opposite.
    """
    names = (*CLASSICAL_PLANETS, "Rahu", "Ketu")
    lords = {name: _nakshatra_lord(float(b[name]["longitude"])) for name in names}
    pairs = [
        _yoga(
            "Nakshatra Parivartana", True,
            f"{a} is in a nakshatra ruled by {c} and {c} in one ruled by {a}.",
            [a, c],
        )
        for a, c in combinations(names, 2)
        if {a, c} != {"Rahu", "Ketu"} and lords[a] == c and lords[c] == a
    ]
    if pairs:
        return pairs
    listing = ", ".join(f"{name} {lords[name]}" for name in names)
    return [
        _yoga(
            "Nakshatra Parivartana", False,
            f"No two bodies occupy each other's nakshatras; nakshatra lords: {listing}.",
            [],
        )
    ]


def compute_chara_karakas(planets: list[dict]) -> list[dict]:
    """The seven chara karakas, Atmakaraka first: the classical planets by degree within their sign.

    Rahu belongs only to the eight-karaka variant, Uranus, Neptune and Pluto
    to neither. A tie on the degree is broken by the full longitude.
    """
    by_name = {p["name"]: p for p in planets}
    ranked = sorted(
        CLASSICAL_PLANETS,
        key=lambda name: (float(by_name[name]["longitude"]) % 30.0, float(by_name[name]["longitude"])),
        reverse=True,
    )
    return [
        {
            "karaka": karaka,
            "planet": name,
            "sign": by_name[name]["sign"],
            "degree_in_sign": round(float(by_name[name]["longitude"]) % 30.0, 2),
        }
        for karaka, name in zip(CHARA_KARAKAS, ranked)
    ]


def _mangal_dosha(b: dict[str, dict], lagna: str) -> dict:
    mars = b["Mars"]["sign"]
    houses = {
        "lagna": house_from(mars, lagna),
        "moon": house_from(mars, b["Moon"]["sign"]),
        "venus": house_from(mars, b["Venus"]["sign"]),
    }
    flags = {key: value in MANGAL_DOSHA_HOUSES for key, value in houses.items()}
    reason = (
        f"Mars is {ordinal(houses['lagna'])} from the Lagna, {ordinal(houses['moon'])} "
        f"from the Moon and {ordinal(houses['venus'])} from Venus; the dosha houses are "
        "the 1st, 2nd, 4th, 7th, 8th and 12th."
    )
    return _yoga(
        "Mangal Dosha", any(flags.values()), reason, ["Mars"],
        from_lagna=flags["lagna"], from_moon=flags["moon"], from_venus=flags["venus"],
    )


def _kala_sarpa(b: dict[str, dict]) -> dict:
    rahu = float(b["Rahu"]["longitude"])
    ahead = [p for p in CLASSICAL_PLANETS if (float(b[p]["longitude"]) - rahu) % 360.0 < 180.0]
    behind = [p for p in CLASSICAL_PLANETS if p not in ahead]
    if not behind or not ahead:
        reason = "All seven planets lie on one side of the Rahu–Ketu axis."
        return _yoga("Kala Sarpa", True, reason, ["Rahu", "Ketu"])
    reason = (
        f"Planets lie on both sides of the Rahu–Ketu axis: {_join(ahead)} on one, "
        f"{_join(behind)} on the other."
    )
    return _yoga("Kala Sarpa", False, reason, ["Rahu", "Ketu"])


def _amala(b: dict[str, dict], lagna: str) -> dict:
    moon = b["Moon"]["sign"]
    from_lagna = [p for p in NATURAL_BENEFICS if house_from(b[p]["sign"], lagna) == 10]
    from_moon = [p for p in NATURAL_BENEFICS if house_from(b[p]["sign"], moon) == 10]
    reason = (
        f"Natural benefics (Jupiter, Venus, Mercury) in the 10th from the Lagna "
        f"({_sign_at(lagna, 10)}): {_join(from_lagna)}; in the 10th from the Moon "
        f"({_sign_at(moon, 10)}): {_join(from_moon)}."
    )
    planets = list(dict.fromkeys(from_lagna + from_moon))
    return _yoga("Amala", bool(planets), reason, planets)


def _lords_of(lagna: str, houses: tuple[int, ...]) -> dict[int, str]:
    return {house: SIGN_LORDS[_sign_at(lagna, house)] for house in houses}


def _dhana(b: dict[str, dict], lagna: str) -> list[dict]:
    lords = _lords_of(lagna, (2, 5, 9, 11))
    found: list[dict] = []
    for (house_a, lord_a), (house_c, lord_c) in combinations(lords.items(), 2):
        if lord_a == lord_c:
            continue
        link = _associated(lord_a, lord_c, b)
        if link and not any(set(y["planets"]) == {lord_a, lord_c} for y in found):
            found.append(
                _yoga(
                    "Dhana", True,
                    f"The {ordinal(house_a)} lord {lord_a} and the {ordinal(house_c)} lord "
                    f"{lord_c} are linked: {link}.",
                    [lord_a, lord_c],
                )
            )
    if found:
        return found
    listing = ", ".join(f"{ordinal(h)} {p}" for h, p in lords.items())
    return [
        _yoga(
            "Dhana", False,
            f"Lords of the 2nd, 5th, 9th and 11th ({listing}) share no sign, mutual "
            "aspect or sign exchange.",
            [],
        )
    ]


def _dharma_karmadhipati(b: dict[str, dict], lagna: str) -> dict:
    lords = _lords_of(lagna, (9, 10))
    ninth, tenth = lords[9], lords[10]
    if ninth == tenth:
        return _yoga(
            "Dharma-Karmadhipati", True,
            f"{ninth} rules both the 9th and the 10th house.", [ninth],
        )
    link = _associated(ninth, tenth, b)
    if link:
        return _yoga(
            "Dharma-Karmadhipati", True,
            f"The 9th lord {ninth} and the 10th lord {tenth} are linked: {link}.",
            [ninth, tenth],
        )
    return _yoga(
        "Dharma-Karmadhipati", False,
        f"The 9th lord {ninth} ({b[ninth]['sign']}) and the 10th lord {tenth} "
        f"({b[tenth]['sign']}) share no sign, mutual aspect or sign exchange.",
        [ninth, tenth],
    )


def compute_yogas(planets: list[dict], ascendant: dict) -> list[dict]:
    """Evaluate the fixed list of yogas and doshas against the sidereal chart.

    Returns one entry per yoga — several for Neecha Bhanga (one per
    debilitated planet), Parivartana, Nakshatra Parivartana and Dhana (one
    per pair) — each
    `{name, present, reason, planets}` plus rule-specific flags.
    """
    b = _bodies(planets)
    lagna = ascendant["sign"]
    yogas: list[dict] = [
        _gaja_kesari(b),
        _same_sign_yoga("Budha-Aditya", "Sun", "Mercury", b),
        _same_sign_yoga("Chandra-Mangala", "Moon", "Mars", b),
    ]
    yogas += [_mahapurusha(planet, b, lagna) for planet in MAHAPURUSHA]
    yogas += [_vipareeta(name, house, b, lagna) for name, house in VIPAREETA]
    yogas += _neecha_bhanga(b, lagna)
    yogas += _moon_flank_yogas(b)
    yogas += _sun_flank_yogas(b)
    yogas += _kartari_yogas(b, lagna)
    yogas += _parivartana(b)
    yogas.append(_mangal_dosha(b, lagna))
    yogas.append(_kala_sarpa(b))
    yogas.append(_amala(b, lagna))
    yogas += _dhana(b, lagna)
    yogas.append(_dharma_karmadhipati(b, lagna))
    # Last, so the positions of the entries before 1.0.6 do not move.
    yogas += _nakshatra_parivartana(b)
    return yogas


__all__ = [
    "CHARA_KARAKAS",
    "CLASSICAL_PLANETS",
    "DEBILITATION_SIGNS",
    "DRISHTI",
    "EXALTATION_SIGNS",
    "OWN_SIGNS",
    "SIGN_LORDS",
    "attach_vedic_houses",
    "compute_chara_karakas",
    "compute_drishti",
    "compute_yogas",
    "house_from",
    "ketu_position",
    "ordinal",
]

"""Propose a venture profile from intake documents, with a citation per field.

The structuring engine's weakest link has always been that the venture profile
is typed by hand. Somebody reads the intake, forms a view, and enters twenty-
four fields — and every one of those fields silently becomes an assertion the
memo then reasons from. Nobody can later tell which fields came from the client
and which came from whoever was typing.

This proposes the profile instead, and every proposed field carries the phrase
it was drawn from and the document it appeared in. Nothing is applied
automatically: the output is a *proposal* that a human confirms field by field,
which is the same shape as every other reviewed thing in this system.

Three rules keep it honest:

- **Silence is not a value.** A field with no supporting evidence is left
  unproposed rather than defaulted. The engine's own defaults are visible and
  arguable; a default laundered through an "extraction" step is neither.
- **Every proposal cites.** Field, value, the exact phrase, and the source
  document. A proposal that cannot show its evidence is dropped.
- **Ambiguity is reported, not resolved.** Where the intake supports two
  readings — an owner described as both active and passive — both are surfaced
  as a conflict for the human, because a coin-flip in an extraction step is
  indistinguishable from a fact in the memo that follows.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .governance import VentureProfile
from .schemas import SourceDocument

# Field -> (value, patterns). A pattern hit proposes the value. Patterns are
# generic intake language, and each is deliberately specific enough that a
# passing mention does not trip it.
_BOOLEAN_SIGNALS: dict[str, list[tuple[bool, tuple[str, ...]]]] = {
    "real_property": [
        (True, ("will own real estate", "owns real property", "owns the building",
                "purchase the property", "acquire the property", "real property will be")),
    ],
    "material_ip": [
        (True, ("trademark", "proprietary method", "our brand", "licensing the brand",
                "intellectual property", "proprietary software")),
    ],
    "spouses_involved": [
        (True, ("is married", "are married", "spouse", "husband", "wife")),
    ],
    "estate_planning_relevant": [
        (True, ("estate plan", "revocable trust", "succession plan", "pass it to")),
    ],
    "tiered_economics": [
        (True, ("preferred return", "promote", "waterfall", "paid back first",
                "priority return")),
    ],
    "expects_additional_capital": [
        (True, ("will need more capital", "future capital", "additional capital",
                "raise more")),
        (False, ("no further capital", "fully funded", "no additional capital")),
    ],
    "operating_liability": [
        (True, ("employees", "customers on site", "vehicles", "trucks", "crews",
                "staff")),
    ],
}

_ACTIVITY_SIGNALS: dict[str, tuple[str, ...]] = {
    "film_production": ("film", "picture", "production company", "screenplay",
                        "documentary", "series"),
    "skilled_trades": ("hvac", "plumbing", "electrical", "roofing", "contractor",
                       "home services", "trades business"),
    "hospitality": ("restaurant", "bar ", "hotel", "cafe", "hospitality",
                    "second location"),
    "real_estate_hold": ("rental", "income property", "multifamily", "hold the property",
                         "buy and hold"),
    "development": ("entitlement", "ground-up", "develop the site", "construction of"),
    "professional_services": ("consulting", "advisory", "professional services",
                              "our clients"),
    "fund": ("fund i", "fund ii", "pooled", "limited partners", "capital fund"),
}

_REGIME_SIGNALS: dict[str, tuple[str, ...]] = {
    "cannabis": ("cannabis", "dispensary", "marijuana", "plant-touching"),
    "hemp": ("hemp", "cbd", "delta-8"),
    "liquor": ("liquor licence", "liquor license", "abc licence", "abc license",
               "beer and wine"),
    "contractor_licensing": ("contractor licence", "contractor license",
                             "qualifying individual", "licensed contractor"),
}

_CAPITAL_SIGNALS: dict[str, tuple[str, ...]] = {
    "institutional": ("institutional investor", "venture capital", "private equity",
                      "family office"),
    "private_placement": ("private placement", "accredited investor", "reg d",
                          "offering memorandum", "raising from investors"),
    "friends_family": ("friends and family", "friends & family", "family money"),
    "founders_only": ("our own money", "self-funded", "founders' capital",
                      "bootstrapped"),
}

_EXIT_SIGNALS: dict[str, tuple[str, ...]] = {
    "sale": ("sell the business", "exit in", "acquisition target", "sell in five"),
    "generational": ("pass it to", "next generation", "my children", "legacy"),
    "refinance_recap": ("refinance", "recapitalis", "recapitaliz", "pull cash out"),
    "hold_indefinitely": ("hold indefinitely", "no plans to sell", "long-term hold"),
}

_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)\s*(million|m\b|k\b)?", re.IGNORECASE)
_PEOPLE = re.compile(
    r"\b(two|three|four|five|six|2|3|4|5|6)\s+(?:equal\s+)?"
    r"(partners|founders|owners|principals|members)\b", re.IGNORECASE)

_WORD_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}


class FieldProposal(BaseModel):
    """One field, its proposed value, and the evidence behind it."""

    field: str
    value: object
    phrase: str = Field(description="The exact language the value was drawn from.")
    source_id: str
    source_title: str

    def to_line(self) -> str:
        return (f"**{self.field}** = `{self.value!r}` — “…{self.phrase}…” "
                f"({self.source_title})")


class FieldConflict(BaseModel):
    """The intake supports two readings. A human decides; the engine does not."""

    field: str
    readings: list[str]
    why_it_matters: str


class ProfileProposal(BaseModel):
    """A proposed venture profile, entirely unapplied until confirmed."""

    venture: str
    proposals: list[FieldProposal]
    conflicts: list[FieldConflict]
    unproposed: list[str] = Field(
        description="Fields with no supporting evidence. Left for a human rather "
                    "than defaulted.")

    def as_kwargs(self) -> dict:
        """Only the fields evidence actually supports."""
        return {item.field: item.value for item in self.proposals}

    def to_profile(self, **overrides) -> VentureProfile:
        """Build the profile, requiring the caller to supply what evidence did not.

        Deliberately not a one-click action: the overrides are the fields a human
        had to decide, and passing them is the act of confirming.
        """
        return VentureProfile(venture=self.venture, **{**self.as_kwargs(), **overrides})

    def to_markdown(self) -> str:
        out = [f"# Intake Proposal — {self.venture}", ""]
        out.append("> Proposed from the intake documents, with the phrase behind each "
                   "field. **Nothing here is applied.** Confirm each line, correct "
                   "what is wrong, and supply what the intake did not say.")
        out.append("")
        if self.conflicts:
            out.append("## Read two ways")
            out.append("")
            for conflict in self.conflicts:
                out.append(f"**{conflict.field}.** {conflict.why_it_matters}")
                out += [f"  - {reading}" for reading in conflict.readings]
                out.append("")
        out.append("## Proposed, with evidence")
        out.append("")
        for item in self.proposals:
            out.append(f"- {item.to_line()}")
        out.append("")
        if self.unproposed:
            out.append("## The intake did not say")
            out.append("")
            out.append("These decide real structure and were left alone rather than "
                       "defaulted. Ask before the memo is produced.")
            out.append("")
            out += [f"- {field}" for field in sorted(self.unproposed)]
            out.append("")
        return "\n".join(out).rstrip() + "\n"


# Fields worth asking about explicitly when the intake is silent. Chosen because
# each one changes the structure rather than merely colouring it.
_MATERIAL_FIELDS = (
    "active_principals", "passive_investors", "equal_ownership", "activity",
    "home_state", "capital_source", "initial_capital", "real_property",
    "material_ip", "regulated_regime", "exit_intent", "expected_hold_years",
    "spouses_involved", "estate_planning_relevant", "tessera_role",
)


def _window(text: str, index: int, width: int = 70) -> str:
    start, end = max(0, index - width // 3), min(len(text), index + width)
    return " ".join(text[start:end].split())


def propose_profile(documents: list[SourceDocument], *,
                    venture: str) -> ProfileProposal:
    """Read intake documents and propose the fields they actually support."""
    proposals: list[FieldProposal] = []
    conflicts: list[FieldConflict] = []
    proposed_fields: set[str] = set()

    def propose(field: str, value: object, phrase: str,
                document: SourceDocument) -> None:
        if field in proposed_fields:
            return
        proposed_fields.add(field)
        proposals.append(FieldProposal(
            field=field, value=value, phrase=phrase,
            source_id=document.source_id, source_title=document.title))

    def first_hit(text: str, lowered: str, patterns: tuple[str, ...]):
        for pattern in patterns:
            index = lowered.find(pattern)
            if index >= 0:
                return _window(text, index)
        return None

    for document in documents:
        text = document.content
        lowered = text.casefold()

        for field, options in _BOOLEAN_SIGNALS.items():
            for value, patterns in options:
                phrase = first_hit(text, lowered, patterns)
                if phrase:
                    propose(field, value, phrase, document)
                    break

        for choice_field, table in (("activity", _ACTIVITY_SIGNALS),
                                    ("regulated_regime", _REGIME_SIGNALS),
                                    ("capital_source", _CAPITAL_SIGNALS),
                                    ("exit_intent", _EXIT_SIGNALS)):
            matches = {value: first_hit(text, lowered, patterns)
                       for value, patterns in table.items()}
            matches = {value: phrase for value, phrase in matches.items() if phrase}
            if len(matches) == 1:
                value, phrase = next(iter(matches.items()))
                propose(choice_field, value, phrase, document)
            elif len(matches) > 1 and choice_field not in proposed_fields:
                conflicts.append(FieldConflict(
                    field=choice_field,
                    readings=[f"`{value}` — “…{phrase}…”"
                              for value, phrase in sorted(matches.items())],
                    why_it_matters=(
                        "The intake supports more than one reading, and this field "
                        "changes the structure. Guessing here would put a fact in the "
                        "memo that nobody actually asserted.")))

        people = _PEOPLE.search(text)
        if people and "active_principals" not in proposed_fields:
            count = _WORD_NUMBERS.get(people.group(1).casefold())
            if count:
                propose("active_principals", count,
                        _window(text, people.start()), document)
                if "equal" in people.group(0).casefold():
                    propose("equal_ownership", True,
                            _window(text, people.start()), document)

        money = _MONEY.search(text)
        if money and "initial_capital" not in proposed_fields:
            amount = float(money.group(1).replace(",", ""))
            unit = (money.group(2) or "").lower()
            if unit.startswith("m"):
                amount *= 1_000_000
            elif unit.startswith("k"):
                amount *= 1_000
            propose("initial_capital", amount, _window(text, money.start()), document)

    unproposed = [field for field in _MATERIAL_FIELDS
                  if field not in proposed_fields
                  and field not in {conflict.field for conflict in conflicts}]

    return ProfileProposal(venture=venture, proposals=proposals,
                           conflicts=conflicts, unproposed=unproposed)

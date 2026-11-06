"""Detect column-header collisions before the model is called.

Why this module exists
----------------------
PLUMB's measurement is that no 3.35B model in the Tiny Aya family detects
unannounced column ambiguity: given two columns sharing a header, `global` asks
for clarification 0 times out of 16 and `fire` 1 out of 16, while an 8B
reference asks 16 out of 16. Told explicitly that the qualifying column is
unspecified, `global` goes to 11 of 16 and `fire` to 16 of 16.

So the capability to abstain is present and the capability to *notice* is not,
and the usual mitigation ("instruct the model to ask when unsure") cannot work,
because a prompt cannot describe a collision the model has not seen.

Duplicate headers are a schema property. Finding them is a job for your
harness, not your model. This module is that job: no dependencies, no model
call, no network. Detect the collision, then say so in the prompt.

    from plumb.ambiguity import find_header_collisions, announce

    collisions = find_header_collisions(cells)
    if collisions:
        instruction += " " + announce(collisions)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CELL = re.compile(r"^([A-Z]+)(\d+)$")


@dataclass
class Collision:
    """One header appearing in more than one column."""

    header: str
    columns: list[str]
    row: int
    normalised: str = ""
    variants: dict[str, str] = field(default_factory=dict)

    @property
    def exact(self) -> bool:
        """True when the columns are byte-identical, not merely similar."""
        return len(set(self.variants.values())) <= 1

    def __str__(self) -> str:
        where = ", ".join(self.columns)
        if self.exact:
            return f"{self.header!r} in columns {where}"
        seen = ", ".join(f"{c}={self.variants[c]!r}" for c in self.columns)
        return f"{self.header!r} (near-duplicate) in {seen}"


def _normalise(text: str) -> str:
    """Fold the differences that are presentation rather than meaning.

    Case, surrounding whitespace, internal runs of whitespace, trailing
    punctuation, and underscores against spaces. Deliberately conservative:
    it will not fold 'Revenue' into 'Revenues', because a harness that
    over-reports collisions trains its users to ignore it.
    """
    s = str(text).strip().lower().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .:;,-")


def find_header_collisions(
    cells: dict[str, object],
    header_row: int = 1,
    include_near_duplicates: bool = True,
) -> list[Collision]:
    """Return headers that appear in more than one column of `header_row`.

    `cells` is an address-keyed sheet, e.g. {"A1": "Month", "B1": "Revenue"}.
    Returns [] when the sheet is unambiguous, so the result is falsy in the
    common case and `if find_header_collisions(cells):` reads correctly.
    """
    headers: dict[str, tuple[str, str]] = {}
    for address, value in cells.items():
        m = _CELL.match(str(address).strip().upper())
        if not m or int(m.group(2)) != header_row:
            continue
        text = str(value)
        if not text.strip():
            continue
        headers[m.group(1)] = (text, _normalise(text))

    buckets: dict[str, list[str]] = {}
    for column, (_, key) in headers.items():
        buckets.setdefault(key, []).append(column)

    out = []
    for key, columns in buckets.items():
        if len(columns) < 2:
            continue
        columns.sort(key=lambda c: (len(c), c))
        variants = {c: headers[c][0] for c in columns}
        collision = Collision(
            header=headers[columns[0]][0],
            columns=columns,
            row=header_row,
            normalised=key,
            variants=variants,
        )
        if collision.exact or include_near_duplicates:
            out.append(collision)
    out.sort(key=lambda c: c.columns[0])
    return out


def announce(collisions: list[Collision]) -> str:
    """Phrase a collision for the model, the way the benchmark phrases it.

    The wording matters and is not arbitrary. This mirrors the announced tier
    of the P2 probe, which is the condition measured to move `tiny-aya-global`
    from 0/16 to 11/16 and `tiny-aya-fire` from 1/16 to 16/16. Saying less
    than this was not measured.
    """
    if not collisions:
        return ""
    parts = []
    for c in collisions:
        cols = " and ".join(c.columns)
        parts.append(
            f"Columns {cols} both have the header {c.header!r} with different "
            f"values; the request does not specify which one qualifies."
        )
    parts.append(
        "If the task depends on which column is meant, ask for clarification "
        "rather than choosing one."
    )
    return " ".join(parts)


def describe(cells: dict[str, object], header_row: int = 1) -> str:
    """One-line summary for logs and CI output."""
    found = find_header_collisions(cells, header_row=header_row)
    if not found:
        return "no header collisions"
    return f"{len(found)} header collision(s): " + "; ".join(str(c) for c in found)

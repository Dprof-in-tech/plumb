"""Small address-based spreadsheet representation used by the benchmark."""

from __future__ import annotations

import re
from typing import Any

_CELL = re.compile(r"^([A-Z]+)(\d+)$")


def _column_number(column: str) -> int:
    value = 0
    for char in column:
        value = value * 26 + ord(char) - ord("A") + 1
    return value


def _column_name(number: int) -> str:
    chars = []
    while number:
        number, remainder = divmod(number - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def expand_all(addresses: list[str]) -> set[str]:
    expanded: set[str] = set()
    for address in addresses:
        parts = address.upper().split(":")
        if len(parts) == 1:
            expanded.add(parts[0])
            continue
        start, end = (_CELL.match(part) for part in parts)
        if not start or not end:
            raise ValueError(f"invalid cell range: {address}")
        for column in range(_column_number(start.group(1)), _column_number(end.group(1)) + 1):
            for row in range(int(start.group(2)), int(end.group(2)) + 1):
                expanded.add(f"{_column_name(column)}{row}")
    return expanded


class Sheet:
    def __init__(self, cells: dict[str, Any], name: str = "Sheet1") -> None:
        self.name = name
        self.cells = {str(address).upper(): value for address, value in cells.items()}

    def serialise(self) -> str:
        return "\n".join(f"{address}: {value}" for address, value in sorted(self.cells.items()))

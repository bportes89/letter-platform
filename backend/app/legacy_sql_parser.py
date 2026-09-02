"""Parser de dumps phpMyAdmin/MySQL (INSERT) para migração legado."""

from __future__ import annotations

import re
from typing import Any, Iterator


INSERT_HEADER_RE = re.compile(
    r"INSERT INTO `(?P<table>\w+)` \((?P<columns>[^)]+)\)\s*VALUES\s*",
    re.IGNORECASE,
)


def _split_columns(raw: str) -> list[str]:
    return [part.strip().strip("`") for part in raw.split(",")]


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _parse_string(text: str, index: int) -> tuple[str, int]:
    assert text[index] == "'"
    index += 1
    chars: list[str] = []
    while index < len(text):
        ch = text[index]
        if ch == "\\":
            index += 1
            if index < len(text):
                chars.append(text[index])
                index += 1
            continue
        if ch == "'":
            if index + 1 < len(text) and text[index + 1] == "'":
                chars.append("'")
                index += 2
                continue
            return "".join(chars), index + 1
        chars.append(ch)
        index += 1
    raise ValueError("String SQL não terminada")


def _parse_value(text: str, index: int) -> tuple[Any, int]:
    index = _skip_ws(text, index)
    if index >= len(text):
        raise ValueError("Valor SQL inesperado no fim do bloco")
    ch = text[index]
    if ch == "'":
        return _parse_string(text, index)
    if text.startswith("NULL", index):
        return None, index + 4
    start = index
    if ch == "-":
        index += 1
    while index < len(text) and (text[index].isdigit() or text[index] == "."):
        index += 1
    token = text[start:index]
    if not token or token == "-":
        raise ValueError(f"Token numérico inválido em {start}")
    if "." in token:
        return float(token), index
    return int(token), index


def _parse_tuple(text: str, index: int) -> tuple[list[Any], int]:
    index = _skip_ws(text, index)
    if text[index] != "(":
        raise ValueError("Tupla SQL deve iniciar com '('")
    index += 1
    values: list[Any] = []
    while True:
        index = _skip_ws(text, index)
        if index < len(text) and text[index] == ")":
            return values, index + 1
        value, index = _parse_value(text, index)
        values.append(value)
        index = _skip_ws(text, index)
        if index < len(text) and text[index] == ",":
            index += 1
            continue
        if index < len(text) and text[index] == ")":
            return values, index + 1
        raise ValueError("Tupla SQL malformada")


def parse_values_block(block: str) -> list[list[Any]]:
    rows: list[list[Any]] = []
    index = 0
    while index < len(block):
        index = _skip_ws(block, index)
        if index >= len(block):
            break
        if block[index] != "(":
            index += 1
            continue
        row, index = _parse_tuple(block, index)
        rows.append(row)
        index = _skip_ws(block, index)
        if index < len(block) and block[index] == ",":
            index += 1
    return rows


def iter_table_rows(sql: str, table: str) -> Iterator[dict[str, Any]]:
    for match in INSERT_HEADER_RE.finditer(sql):
        if match.group("table") != table:
            continue
        columns = _split_columns(match.group("columns"))
        start = match.end()
        end = sql.find(";", start)
        if end < 0:
            end = len(sql)
        block = sql[start:end]
        for values in parse_values_block(block):
            if len(values) != len(columns):
                raise ValueError(
                    f"Tabela {table}: colunas={len(columns)} valores={len(values)}"
                )
            yield dict(zip(columns, values, strict=True))


def load_table(sql: str, table: str) -> list[dict[str, Any]]:
    return list(iter_table_rows(sql, table))

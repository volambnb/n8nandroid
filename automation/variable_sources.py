"""Read one value from a local CSV or XLSX file for a Variables node."""

from __future__ import annotations

import csv
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


_SS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _column_index(column: str, headers: list[str] | None) -> int:
    name = str(column).strip()
    if not name:
        raise ValueError("Choose a CSV/XLSX column for the variable.")
    if headers:
        for index, header in enumerate(headers):
            if header.strip().casefold() == name.casefold():
                return index
    if name.isdecimal():
        index = int(name) - 1
    elif re.fullmatch(r"[A-Za-z]{1,3}", name):
        index = 0
        for letter in name.upper():
            index = index * 26 + ord(letter) - ord("A") + 1
        index -= 1
    else:
        raise ValueError(f"CSV/XLSX column was not found: {name}")
    if index < 0 or index > 16383:
        raise ValueError("CSV/XLSX column is out of range.")
    return index


def _csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        return list(csv.reader(handle, dialect))


def _xlsx_rows(path: Path, sheet_name: str) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib.get("Id"): rel.attrib.get("Target", "") for rel in relationships.findall(f"{_PKG_REL}Relationship")}
        sheets = workbook.find(f"{_SS}sheets")
        if sheets is None or not list(sheets):
            raise ValueError("XLSX workbook has no sheets.")
        sheet = next((item for item in sheets if item.attrib.get("name", "").casefold() == sheet_name.casefold()), None) if sheet_name else list(sheets)[0]
        if sheet is None:
            raise ValueError(f"XLSX sheet was not found: {sheet_name}")
        target = targets.get(sheet.attrib.get(f"{_REL}id"), "")
        if not target:
            raise ValueError("XLSX worksheet link is missing.")
        member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        if not member.startswith("xl/") or member not in archive.namelist():
            raise ValueError("XLSX worksheet path is invalid.")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            string_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(part.text or "" for part in cell.iter(f"{_SS}t")) for cell in string_root.findall(f"{_SS}si")]
        root = ET.fromstring(archive.read(member))
        sheet_data = root.find(f"{_SS}sheetData")
        if sheet_data is None:
            return []
        rows: list[list[str]] = []
        for row in sheet_data.findall(f"{_SS}row"):
            line: list[str] = []
            for cell in row.findall(f"{_SS}c"):
                address = cell.attrib.get("r", "")
                letters = re.match(r"[A-Za-z]+", address)
                if letters:
                    index = _column_index(letters.group(), None)
                else:
                    index = len(line)
                if index > 16383:
                    continue
                while len(line) <= index:
                    line.append("")
                kind = cell.attrib.get("t", "")
                value = cell.find(f"{_SS}v")
                if kind == "inlineStr":
                    inline = cell.find(f"{_SS}is")
                    line[index] = "".join(part.text or "" for part in inline.iter(f"{_SS}t")) if inline is not None else ""
                elif kind == "s" and value is not None:
                    string_index = int(value.text or "0")
                    line[index] = shared[string_index] if 0 <= string_index < len(shared) else ""
                elif kind == "b" and value is not None:
                    line[index] = "true" if value.text == "1" else "false"
                elif value is not None:
                    line[index] = value.text or ""
            rows.append(line)
        return rows


def read_variable_cell(file_path: str, *, row_index: int, column: str, sheet_name: str = "", has_header: bool = True) -> str:
    """Read a one-based data row, excluding the optional header row."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise ValueError(f"Variable data file was not found: {path}")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Variable data file exceeds 50 MB.")
    if row_index < 1:
        raise ValueError("Variable data row must start at 1.")
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        rows = _csv_rows(path)
    elif suffix == ".xlsx":
        rows = _xlsx_rows(path, sheet_name)
    else:
        raise ValueError("Variables supports CSV and XLSX files only.")
    headers = rows[0] if has_header and rows else None
    actual_row = row_index if has_header else row_index - 1
    if actual_row >= len(rows):
        raise ValueError(f"Variable data row {row_index} does not exist in {path.name}.")
    index = _column_index(column, headers)
    selected = rows[actual_row]
    if index >= len(selected):
        raise ValueError(f"Column {column} is empty or missing in data row {row_index}.")
    return selected[index]

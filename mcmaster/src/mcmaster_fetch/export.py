"""Turn product records into JSON and CSV files."""

from __future__ import annotations

import csv
import json
from pathlib import Path

BASE_COLUMNS = ["PartNumber", "ProductStatus", "FamilyDescription", "DetailDescription", "Price"]


def links(product: dict) -> dict[str, str]:
    """``Links`` as a ``{Key: Value}`` dict, e.g. ``{"3-D STEP": "/v1/cad/..."}``."""
    return {l["Key"]: l["Value"] for l in product.get("Links") or [] if "Key" in l and "Value" in l}


def specs(product: dict) -> dict[str, str]:
    """``Specifications`` flattened to ``{Attribute: "v1; v2"}``."""
    out = {}
    for spec in product.get("Specifications") or []:
        attr = spec.get("Attribute")
        if attr:
            out[attr] = "; ".join(str(v) for v in spec.get("Values") or [])
    return out


def format_price(prices: list[dict] | None) -> str:
    """``[{"Amount": 9.46, "MinimumQuantity": 1, "UnitOfMeasure": "Pack"}]`` -> ``"9.46/Pack (min 1)"``."""
    parts = []
    for p in prices or []:
        text = f"{p.get('Amount')}/{p.get('UnitOfMeasure', 'Each')}"
        if p.get("MinimumQuantity") not in (None, 1):
            text += f" (min {p['MinimumQuantity']})"
        parts.append(text)
    return "; ".join(parts)


def to_row(record: dict) -> dict[str, str]:
    product = record["product"]
    row = {col: product.get(col, "") for col in BASE_COLUMNS[:-1]}
    row["Price"] = format_price(record.get("price"))
    row.update(specs(product))
    row["CadFiles"] = "; ".join(record.get("files", []))
    return row


def write_json(records: list[dict], path: Path) -> None:
    path.write_text(json.dumps(records, indent=2) + "\n")


def write_csv(records: list[dict], path: Path) -> None:
    rows = [to_row(r) for r in records]
    columns = list(BASE_COLUMNS)
    for row in rows:
        for key in row:
            if key not in columns and key != "CadFiles":
                columns.append(key)
    columns.append("CadFiles")
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, restval="")
        writer.writeheader()
        writer.writerows(rows)

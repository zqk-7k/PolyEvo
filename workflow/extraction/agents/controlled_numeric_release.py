"""Versioned, evidence-gated release rules for controlled numeric evolution.

Unlike the retired thermal-weight-loss companion prototype, these rules never
turn a measurement condition into a second property.  They only release a
numeric table cell that the existing extraction stages already classified.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from extraction.evaluation.property_views import unified_numeric_records
from extraction.sample_normalization import normalize_sample_label


AGENT_VERSION = "controlled-numeric-release/2.5"
PDI_LABEL = "molecular_weight_distribution"


def _sample_index(candidate: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("sample_id")): dict(item)
        for item in candidate.get("samples") or []
        if isinstance(item, Mapping) and item.get("sample_id")
    }


def _normalized_label(value: Any) -> str:
    return normalize_sample_label(value)


def _evidence_rows(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in item.get("evidence") or [] if isinstance(row, Mapping)]


def _direct_table_cell(item: Mapping[str, Any]) -> dict[str, Any] | None:
    for evidence in _evidence_rows(item):
        locator = evidence.get("table_locator")
        if (
            evidence.get("source_type") == "table"
            and isinstance(locator, Mapping)
            and locator.get("table_id")
            and locator.get("cell_id")
            and locator.get("cell_value") is not None
        ):
            return evidence
    return None


def _is_pdi_column(value: Any) -> bool:
    text = _normalized_label(value)
    text = re.sub(r"⟦sup:[^⟧]*⟧", "", text)
    tokens = {token for token in text.split("|") if token}
    return bool(tokens & {"pdi", "mw/mn", "đ"})


def _cell_matches_value(item: Mapping[str, Any], evidence: Mapping[str, Any]) -> bool:
    locator = evidence.get("table_locator")
    if not isinstance(locator, Mapping):
        return False
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", str(locator.get("cell_value") or ""))
    try:
        cell_value = float(match.group().replace(",", ".")) if match else None
        item_value = float(item.get("value_min"))
    except (TypeError, ValueError):
        return False
    return cell_value is not None and math.isclose(
        cell_value, item_value, rel_tol=0.0, abs_tol=1e-8
    )


def _row_matches_sample(
    item: Mapping[str, Any], sample: Mapping[str, Any]
) -> bool:
    evidence = _direct_table_cell(item)
    locator = evidence.get("table_locator") if evidence else None
    row_label = locator.get("row_label") if isinstance(locator, Mapping) else None
    normalized_row = _normalized_label(row_label)
    aliases = {
        _normalized_label(sample.get("sample_label_raw")),
        _normalized_label(sample.get("polymer_name")),
    }
    aliases.discard("")
    return bool(normalized_row and normalized_row in aliases)


def _is_pdi_candidate(item: Mapping[str, Any]) -> bool:
    evidence = _direct_table_cell(item)
    locator = evidence.get("table_locator") if evidence else None
    return (
        item.get("publication_status") == "unresolved"
        and item.get("reason") == "not_in_specialized_scope"
        and str(item.get("semantic_label") or "") == PDI_LABEL
        and item.get("value_min") is not None
        and evidence is not None
        and isinstance(locator, Mapping)
        and _is_pdi_column(locator.get("column_label"))
        and _cell_matches_value(item, evidence)
    )


def _structured_sample_label(
    item: Mapping[str, Any],
    table_contexts: Mapping[str, Mapping[str, Any]],
) -> str | None:
    """Recover a sample cell only when an independent table index is proven.

    A merged row label such as ``3 | P1-PEG350`` is not edited from its string
    shape alone.  The source table must contain both an explicit ``no.`` header
    and an explicit polymer/sample header, and the target row must contain the
    same numeric index and sample text as the merged label.
    """

    evidence = _direct_table_cell(item)
    locator = evidence.get("table_locator") if evidence else None
    if not isinstance(locator, Mapping):
        return None
    table_id = str(locator.get("table_id") or "")
    try:
        row_index = int(locator.get("row_index"))
    except (TypeError, ValueError):
        return None
    table = table_contexts.get(table_id)
    if not isinstance(table, Mapping):
        return None
    cells = [
        cell for cell in table.get("table_cells") or [] if isinstance(cell, Mapping)
    ]
    index_headers: list[tuple[int, int]] = []
    sample_headers: list[tuple[int, int]] = []
    for cell in cells:
        try:
            cell_row = int(cell.get("row_index"))
            cell_column = int(cell.get("column_index"))
        except (TypeError, ValueError):
            continue
        header = re.sub(r"[^a-z0-9]+", "", str(cell.get("text") or "").casefold())
        if header in {"no", "number", "index"}:
            index_headers.append((cell_row, cell_column))
        if header in {
            "resultantpolymer",
            "polymer",
            "samplename",
            "sample",
            "material",
        }:
            sample_headers.append((cell_row, cell_column))
    compatible = [
        (header_row, index_column, sample_column)
        for header_row, index_column in index_headers
        for sample_header_row, sample_column in sample_headers
        if header_row == sample_header_row and header_row < row_index
    ]
    if len(compatible) != 1:
        return None
    _, index_column, sample_column = compatible[0]
    index_values = [
        str(cell.get("text") or "").strip()
        for cell in cells
        if cell.get("row_index") == row_index and cell.get("column_index") == index_column
    ]
    sample_values = [
        str(cell.get("text") or "").strip()
        for cell in cells
        if cell.get("row_index") == row_index and cell.get("column_index") == sample_column
    ]
    if len(index_values) != 1 or len(sample_values) != 1:
        return None
    all_indices = [
        str(cell.get("text") or "").strip()
        for cell in cells
        if isinstance(cell.get("row_index"), int)
        and cell.get("row_index") > compatible[0][0]
        and cell.get("column_index") == index_column
        and re.fullmatch(r"\d+", str(cell.get("text") or "").strip())
    ]
    normalized_sample = _normalized_label(sample_values[0])
    all_samples = [
        _normalized_label(cell.get("text"))
        for cell in cells
        if isinstance(cell.get("row_index"), int)
        and cell.get("row_index") > compatible[0][0]
        and cell.get("column_index") == sample_column
        and _normalized_label(cell.get("text"))
    ]
    if all_indices.count(index_values[0]) != 1 or all_samples.count(normalized_sample) != 1:
        return None
    match = re.fullmatch(
        r"\s*(\d+)\s*\|\s*(.+?)\s*",
        str(locator.get("row_label") or ""),
    )
    if (
        match is None
        or match.group(1) != index_values[0]
        or _normalized_label(match.group(2)) != _normalized_label(sample_values[0])
    ):
        return None
    return sample_values[0]


def _unique_row_label_sample(
    item: Mapping[str, Any],
    samples: Mapping[str, Mapping[str, Any]],
    table_contexts: Mapping[str, Mapping[str, Any]],
) -> tuple[str | None, str]:
    evidence = _direct_table_cell(item)
    locator = evidence.get("table_locator") if evidence else None
    row_label = str(locator.get("row_label") or "") if isinstance(locator, Mapping) else ""
    normalized_row = _normalized_label(row_label)
    resolution_basis = "exact_table_row_label"
    if not normalized_row or not any(
        normalized_row
        in {
            _normalized_label(sample.get("sample_label_raw")),
            _normalized_label(sample.get("polymer_name")),
        }
        for sample in samples.values()
    ):
        structured_label = _structured_sample_label(item, table_contexts)
        if structured_label:
            normalized_row = _normalized_label(structured_label)
            resolution_basis = "structured_no_and_sample_columns"
    if not normalized_row:
        return None, "missing_row_label"
    matches: list[str] = []
    for sample_id, sample in samples.items():
        aliases = {
            _normalized_label(sample.get("sample_label_raw")),
            _normalized_label(sample.get("polymer_name")),
        }
        aliases.discard("")
        if normalized_row in aliases:
            matches.append(sample_id)
    unique = sorted(set(matches))
    if len(unique) == 1:
        return unique[0], resolution_basis
    return None, "row_label_ambiguous" if unique else "row_label_unmatched"


def _released_pdi(
    source: Mapping[str, Any],
    *,
    sample_id: str,
    rule_id: str,
    resolution_basis: str,
) -> dict[str, Any]:
    evidence_rows = _evidence_rows(source)
    locator = (_direct_table_cell(source) or {}).get("table_locator")
    property_name_raw = (
        str(locator.get("column_label"))
        if isinstance(locator, Mapping) and locator.get("column_label")
        else "PDI"
    )
    return {
        "property_id": f"evo_{rule_id}_{source.get('specialized_id')}",
        "property_name_raw": property_name_raw,
        "property_name_normalized": "pdi",
        "property_category": "molecular_weight_distribution",
        "value_raw": source.get("value_raw"),
        "value_min": source.get("value_min"),
        "value_max": (
            source.get("value_max")
            if source.get("value_max") is not None
            else source.get("value_min")
        ),
        "unit_raw": "dimensionless",
        "unit_normalized": "dimensionless",
        "sample_id": sample_id,
        "entity_id": source.get("entity_id"),
        "sample_resolution_status": "resolved",
        "source_type": "table",
        "evidence": evidence_rows,
        "evidence_ids": list(source.get("evidence_ids") or []),
        "diagnostic_source": "controlled_evolution_release",
        "publication_status": "published",
        "derivation": {
            "rule_id": rule_id,
            "source_specialized_id": source.get("specialized_id"),
            "resolution_basis": resolution_basis,
            "agent_version": AGENT_VERSION,
            "uses_gold_value": False,
            "source_unit_raw": source.get("unit_raw"),
        },
    }


def run_controlled_numeric_release(
    candidate: Mapping[str, Any],
    enabled_rules: set[str] | frozenset[str],
    *,
    table_contexts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    records, inventory = unified_numeric_records(candidate)
    samples = _sample_index(candidate)
    additions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_source_cells: set[str] = set()
    table_contexts = table_contexts or {}
    for item in candidate.get("specialized_property_observations") or []:
        if not isinstance(item, Mapping) or not _is_pdi_candidate(item):
            continue
        evidence = _direct_table_cell(item) or {}
        locator = evidence.get("table_locator") or {}
        cell_id = str(locator.get("cell_id") or "")
        sample_id = str(item.get("sample_id") or "")
        resolution_basis = "existing_resolved_sample"
        rule_id = "release_resolved_pdi_table"
        if (
            rule_id in enabled_rules
            and item.get("sample_resolution_status") == "resolved"
            and sample_id in samples
            and _row_matches_sample(item, samples[sample_id])
        ):
            pass
        elif "resolve_pdi_by_unique_row_label" in enabled_rules:
            sample_id, resolution_basis = _unique_row_label_sample(
                item, samples, table_contexts
            )
            rule_id = "resolve_pdi_by_unique_row_label"
            if sample_id is None:
                rejected.append({
                    "source_specialized_id": item.get("specialized_id"),
                    "rule_id": rule_id,
                    "reason": resolution_basis,
                })
                continue
        else:
            continue
        if cell_id in seen_source_cells:
            rejected.append({
                "source_specialized_id": item.get("specialized_id"),
                "rule_id": "source_cell_uniqueness",
                "reason": "duplicate_source_cell",
            })
            continue
        seen_source_cells.add(cell_id)
        released = _released_pdi(
            item,
            sample_id=sample_id,
            rule_id=rule_id,
            resolution_basis=resolution_basis,
        )
        additions.append(released)
        actions.append({
            "action": "release_existing_direct_table_cell",
            "rule_id": rule_id,
            "source_specialized_id": item.get("specialized_id"),
            "sample_id": sample_id,
            "evidence_ids": list(item.get("evidence_ids") or []),
        })
    return {
        "agent_version": AGENT_VERSION,
        "enabled_rules": sorted(enabled_rules),
        "records": records + additions,
        "additions": additions,
        "actions": actions,
        "rejected": rejected,
        "inventory": inventory | {
            "controlled_additions": len(additions),
            "controlled_rejections": len(rejected),
        },
        "release_policy": {
            "gold_values_visible_to_agent": False,
            "requires_existing_semantic_classification": PDI_LABEL,
            "requires_direct_table_cell": True,
            "requires_resolved_sample": True,
            "requires_pdi_column": True,
            "requires_exact_cell_value": True,
            "requires_row_sample_exact_match": True,
            "table_index_requires_structured_no_and_sample_columns": True,
            "pdi_unit": "dimensionless",
            "condition_as_property_materialization": False,
        },
    }

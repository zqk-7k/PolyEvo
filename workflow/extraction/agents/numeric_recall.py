"""Evidence-governed Agent for numeric-property release and recall recovery."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from extraction.evaluation.property_views import unified_numeric_records


AGENT_VERSION = "numeric-recall-agent/1.0"


def load_memory(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("numeric recall memory must be a mapping")
    return payload


def _element_text(element: Mapping[str, Any]) -> str:
    return " ".join(
        str(element.get(key) or "")
        for key in ("text", "caption", "table_body")
    ).strip()


def _normalized_property(item: Mapping[str, Any]) -> str:
    raw = str(item.get("property_name_normalized") or item.get("property_name_raw") or "")
    return re.sub(r"[^a-z0-9]+", "_", raw.casefold()).strip("_")


def _has_evidence(item: Mapping[str, Any]) -> bool:
    return any(
        isinstance(anchor, Mapping) and anchor.get("block_id")
        for anchor in item.get("evidence") or []
    )


def _normalize_units(
    records: list[dict[str, Any]],
    enabled_rules: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    action_keys: set[tuple[Any, ...]] = set()
    for source in records:
        item = dict(source)
        name = _normalized_property(item)
        raw_unit = str(item.get("unit_normalized") or item.get("unit_raw") or "")
        compact_unit = re.sub(r"\s+", "", raw_unit.casefold())
        target_unit = None
        rule_id = None
        if (
            "water_absorption_mass_fraction" in enabled_rules
            and name in {"water_absorption", "water_uptake"}
            and compact_unit in {"%", "percent"}
        ):
            target_unit = "wt%"
            rule_id = "water_absorption_mass_fraction"
        elif (
            "solution_viscosity_unit_aliases" in enabled_rules
            and name in {"intrinsic_viscosity", "eta_inh", "inh"}
            and compact_unit in {"dl/g", "dlg_1", "dlg1", "dlg-1", "dlg⁻¹"}
        ):
            target_unit = "dl/g"
            rule_id = "solution_viscosity_unit_aliases"
        if target_unit and raw_unit.casefold() != target_unit:
            item["unit_normalized"] = target_unit
            item["diagnostic_source"] = "numeric_agent_unit_normalization"
            action_key = (
                rule_id,
                item.get("sample_id"),
                item.get("property_name_normalized") or item.get("property_name_raw"),
                raw_unit,
                target_unit,
            )
            if action_key not in action_keys:
                action_keys.add(action_key)
                actions.append({
                    "action": "normalize_unit",
                    "rule_id": rule_id,
                    "sample_id": item.get("sample_id"),
                    "property_name": item.get("property_name_normalized") or item.get("property_name_raw"),
                    "before": raw_unit,
                    "after": target_unit,
                })
        normalized.append(item)
    return normalized, actions


def _threshold_contexts(stage0: Mapping[str, Any]) -> list[dict[str, Any]]:
    contexts = []
    for element in stage0.get("elements") or []:
        if not isinstance(element, Mapping) or not element.get("block_id"):
            continue
        text = _element_text(element)
        lowered = text.casefold()
        if "%" in text and any(token in lowered for token in ("weight loss", "gravimetric loss")):
            contexts.append({
                "block_id": element.get("block_id"),
                "page": element.get("page"),
                "bbox": element.get("bbox"),
                "source_type": element.get("type"),
                "source_sentence": text[:1000],
            })
    return contexts


def _explicit_threshold(raw_name: str) -> float | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*(?:weight|mass|gravimetric)?\s*loss",
        raw_name,
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def _context_mentions_threshold(text: str, threshold: float) -> bool:
    token = f"{threshold:g}"
    if re.search(rf"(?<!\d){re.escape(token)}\s*%", text):
        return True
    # Scientific prose commonly shares one percent sign across an enumeration,
    # for example "5 and 50% weight loss".
    return bool(re.search(
        rf"(?<!\d){re.escape(token)}\s*(?:,|and)\s*\d+(?:\.\d+)?\s*%"
        rf"\s*(?:weight|mass|gravimetric)?\s*loss",
        text,
        flags=re.IGNORECASE,
    ))


def _context_threshold(
    item: Mapping[str, Any],
    contexts: list[dict[str, Any]],
) -> tuple[float | None, dict[str, Any] | None]:
    raw_name = str(item.get("property_name_raw") or "")
    explicit = _explicit_threshold(raw_name)
    if explicit is not None:
        context = next(
            (
                entry
                for entry in contexts
                if _context_mentions_threshold(entry["source_sentence"], explicit)
            ),
            None,
        )
        return explicit, context

    compact_name = re.sub(r"[^a-z0-9]+", "", raw_name.casefold())
    for context in contexts:
        text = context["source_sentence"]
        lowered = text.casefold()
        if "t10" in compact_name:
            if re.search(r"10\s*%\s*(?:weight|gravimetric|mass)?\s*loss", lowered):
                return 10.0, context
        elif compact_name in {"ti", "tic"} or compact_name.startswith("tic"):
            if re.search(r"2\s*%\s*(?:weight|gravimetric|mass)?\s*loss", lowered):
                return 2.0, context
        elif compact_name.startswith("td"):
            match = re.search(
                r"(?:thermal decomposition temperatures?|t\s*_?\s*d.{0,30})"
                r".{0,240}?(?:at|measured by)\s*(\d+(?:\.\d+)?)\s*%\s*weight loss",
                lowered,
            )
            if match:
                return float(match.group(1)), context
    return None, None


def _thermal_weight_loss_companions(
    records: list[dict[str, Any]],
    stage0: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contexts = _threshold_contexts(stage0)
    additions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()
    for item in records:
        if _normalized_property(item) != "thermal_decomposition_temperature":
            continue
        threshold, context = _context_threshold(item, contexts)
        sample_id = str(item.get("sample_id") or "")
        if threshold is None:
            continue
        if not sample_id or not _has_evidence(item) or context is None:
            rejected.append({
                "rule_id": "thermal_weight_loss_companion",
                "sample_id": sample_id or None,
                "source_record_id": item.get("property_id") or item.get("point_id"),
                "reason": "missing_sample_or_direct_evidence",
            })
            continue
        key = (sample_id, threshold)
        if key in seen:
            continue
        seen.add(key)
        source_evidence = [dict(anchor) for anchor in item.get("evidence") or [] if isinstance(anchor, Mapping)]
        companion = {
            "property_id": f"agent_weight_loss_{sample_id}_{threshold:g}".replace(".", "p"),
            "property_name_raw": "thermal decomposition weight loss",
            "property_name_normalized": "thermal_decomposition_weight_loss",
            "property_category": "thermal_property",
            "value_raw": f"{threshold:g}",
            "value_min": threshold,
            "value_max": threshold,
            "unit_raw": "%",
            "unit_normalized": "%",
            "sample_id": sample_id,
            "entity_id": item.get("entity_id"),
            "sample_resolution_status": item.get("sample_resolution_status"),
            "evidence": source_evidence + [context],
            "evidence_ids": list(item.get("evidence_ids") or []),
            "diagnostic_source": "numeric_agent_companion_fact",
            "publication_status": "published",
            "derivation": {
                "rule_id": "thermal_weight_loss_companion",
                "source_record_id": item.get("property_id") or item.get("point_id"),
                "agent_version": AGENT_VERSION,
            },
        }
        additions.append(companion)
        actions.append({
            "action": "materialize_companion_fact",
            "rule_id": "thermal_weight_loss_companion",
            "sample_id": sample_id,
            "threshold": threshold,
            "source_record_id": item.get("property_id") or item.get("point_id"),
            "context_block_id": context.get("block_id"),
        })
    return additions, actions, rejected


def run_numeric_recall_agent(
    candidate: Mapping[str, Any],
    stage0: Mapping[str, Any],
    memory: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the specialist Agent without consulting evaluation anchors."""
    records, inventory = unified_numeric_records(candidate)
    enabled_rules = {
        str(rule)
        for rule in memory.get("enabled_rules") or []
    }
    records, unit_actions = _normalize_units(records, enabled_rules)
    additions: list[dict[str, Any]] = []
    companion_actions: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if "thermal_weight_loss_companion" in enabled_rules:
        additions, companion_actions, rejected = _thermal_weight_loss_companions(records, stage0)
    return {
        "agent_version": AGENT_VERSION,
        "memory_version": memory.get("memory_version"),
        "records": records + additions,
        "inventory": inventory | {
            "agent_additions": len(additions),
            "agent_unit_normalizations": len(unit_actions),
            "agent_rejections": len(rejected),
        },
        "actions": unit_actions + companion_actions,
        "rejected": rejected,
        "release_policy": {
            "anchor_values_visible_to_agent": False,
            "requires_sample_id": True,
            "requires_direct_record_evidence": True,
            "requires_context_evidence_for_companion_fact": True,
        },
    }


def write_agent_result(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

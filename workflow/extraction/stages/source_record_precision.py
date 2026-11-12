"""Repair table-addressed records from their own source, never reference answers.

Preserve the original cell in audit provenance. Do not invent sample IDs, units
or treatments. Ambiguous source conflicts are reported, not silently resolved.
"""
from __future__ import annotations

import copy
import json
import re

from stages.stage4_direct_table_supplement import plain, table_cell_scalar, header_applies, evidence, canonical_unit

VERSION = "1.0.2"


def _family(name):
    text = re.sub(r"[\s_${}\\]", "", plain(name)).casefold()
    # A heat-capacity jump AT Tg is not a temperature response. Broad
    # transition group headings must not truncate J g^-1 K^-1 to K.
    if re.search(r"heat.?capacity|specific.?heat|(?:delta|Δ|∆)c_?p", text):
        return None
    # TGA-5% is a loss-temperature response, not Tg. The percent token
    # denotes its criterion and must not displace a printed Celsius unit.
    if re.search(r"\btga(?:[−-]?\d|\b)", text):
        return "td"
    if re.search(r"heat.?of.?fusion|enthalpy|δh|deltah", text):
        return "enthalpy"
    if re.search(r"glass.?transition|(?<![a-z])tg(?![a-z])", text):
        return "tg"
    if re.search(r"melting|tm", text):
        return "tm"
    if re.search(r"decomposition|degradation|thermaltransition|\btd\b|\bt\d+\b", text):
        return "td"
    return None


def _printed_unit(text):
    text = plain(text).replace("℃", "°C")
    match = re.search(r"(?<![A-Za-z])(?:mJ/mg|J/g|kJ/kg|J/mol|kJ/mol|°\s*C|K)(?![A-Za-z])", text)
    if match and match[0].replace(" ", "") in {"K", "°C"}:
        tail = text[match.end():]
        if re.match(r"\s*(?:\^\s*)?(?:[-−]\s*1|⁻¹)", tail):
            return None
    return match[0].replace(" ", "") if match else None


def _source_header_unit(headers, caption, family):
    units = [(h["row_index"], _printed_unit(h["text"])) for h in headers if _printed_unit(h["text"])]
    if units:
        deepest = max(d for d, _ in units)
        targets = {u for d, u in units if d == deepest}
        return next(iter(targets)) if len(targets) == 1 else None
    # A global caption unit is used only for an explicitly thermal caption,
    # not a preparation temperature or a mixed-unit properties table.
    if family in {"tg", "tm", "td"} and re.search(r"\(\s*°\s*C\s*\)\s*$", plain(caption)):
        if re.search(r"T\s*_?\s*[gmd]|transition|melting|decomposition", plain(caption), re.I):
            return "°C"
    return None


def _context(record):
    context = record.get("measurement_context")
    if context is None:
        context = {"condition_status": "reported", "other_conditions": {}}
        record["measurement_context"] = context
    context["condition_status"] = "reported"
    context.setdefault("other_conditions", {})
    context.setdefault("other_condition_evidence", {})
    return context


def _repair_prose_unit(record, sources, family, path, changes):
    if family not in {"tg", "tm", "td"}:
        return
    raw = str(record.get("value_raw") or "")
    candidates = []
    for ev in record.get("evidence") or []:
        block = sources.get(ev.get("block_id"), {})
        quote = str(ev.get("source_sentence") or "")
        if block.get("type") != "text" or not quote or quote not in str(block.get("text", "")):
            continue
        match = re.search(r"(?<![\d.])" + re.escape(raw) + r"\s*(degree(?:s)?\s+Kelvin|Kelvin|°C|K)(?![A-Za-z])", quote, re.I)
        if match:
            candidates.append((match[1], "K" if "kelvin" in match[1].casefold() or match[1] == "K" else "°C", ev))
    if len({(raw_unit, unit) for raw_unit, unit, _ in candidates}) != 1:
        return
    raw_unit, unit, ev = candidates[0]
    current = record.get("unit_raw") or record.get("unit_normalized")
    if canonical_unit(current) == unit:
        return
    context = _context(record)
    context["other_conditions"]["precision_original_unit"] = str(current or "")
    context["other_conditions"]["source_property_unit"] = raw_unit
    context["other_condition_evidence"]["source_property_unit"] = [ev]
    record["unit_raw"], record["unit_normalized"] = raw_unit, unit
    changes.append({"path": path, "kind": "prose_unit", "before": current, "after": raw_unit, "source_block_id": ev["block_id"]})


def _sign_witnesses(stage0, row, family, value):
    """Explicit named thermal assignment, same mantissa, opposite sign only."""
    if not row or family not in {"tg", "tm"} or value <= 0:
        return []
    marker = r"(?:T\s*_?\s*" + family[-1] + r"\b|" + (
        r"glass[ -]?transition(?: temperature)?" if family == "tg" else r"melting (?:point|temperature)") + r")"
    witnesses = []
    for block in stage0.get("elements", []):
        if block.get("type") != "text" or re.search(r"references|bibliography", str(block.get("section") or ""), re.I):
            continue
        text = plain(block.get("text", ""))
        subject_matches = list(re.finditer(r"(?<![\w])" + re.escape(plain(row)) + r"(?![\w])", text, re.I))
        for subject in subject_matches:
            # A semicolon or sentence end prevents inheriting another sample.
            tail = re.split(r";|\.\s+(?=[A-Z])", text[subject.end():subject.end() + 220], maxsplit=1)[0]
            # Explicit negation prevents using a rejected assignment.
            if re.search(r"\b(?:not|incorrect|erroneous)\b", tail, re.I):
                continue
            for prop in re.finditer(marker, tail, re.I):
                after = tail[prop.end():prop.end() + 45]
                m = re.search(r"([−-]\s*\d(?:[\d\s]*\.[\d\s]+|[\d\s]*))\s*(?:\^\s*)?°\s*C", after)
                if (not m or re.search(r"[A-Za-z0-9]", after[:m.start()])
                        or abs(float(re.sub(r"\s", "", m[1]).replace("−", "-"))) != value):
                    continue
                # Require this literal numerical text in the original block.
                literal = m[1].strip()
                if literal not in block.get("text", ""):
                    continue
                witnesses.append((block, literal, -value))
    return witnesses


def repair_source_records(stage4, stage0, *, merge_duplicates=True):
    output = copy.deepcopy(stage4)
    sources = {b["block_id"]: b for b in stage0.get("elements", [])}
    changes, conflicts = [], []
    records = [(r, None, f"{key}[{i}]") for key in ("properties", "specialized_property_observations")
               for i, r in enumerate(output.get(key) or [])]
    records += [(p, s, f"property_series[{i}].points[{j}]")
                for i, s in enumerate(output.get("property_series") or [])
                for j, p in enumerate(s.get("points") or [])]
    for record, parent, path in records:
        name = (parent or record).get("property_name_normalized") or (parent or record).get("property_name_raw", "")
        family = _family(name)
        if family is None:
            continue
        value = table_cell_scalar(record.get("value_raw") or "")
        if value is None or record.get("value_max") not in (None, value):
            continue
        # Respect prior scaling, interval interpretation and normalization.
        if record.get("value_min") not in (None, value):
            continue
        candidates = []
        for ev in record.get("evidence") or []:
            loc = ev.get("table_locator") or {}
            source = sources.get(ev.get("block_id"), {})
            if source.get("type") != "table" or loc.get("table_id") != source.get("block_id"):
                continue
            cells = source.get("table_cells") or []
            cell = next((c for c in cells if c.get("cell_id") == loc.get("cell_id")), None)
            if not cell or table_cell_scalar(cell.get("text", "")) != value:
                continue
            # Header band ends at the FIRST numeric data cell in this column;
            # later rows are never reinterpreted as headings.
            numeric_rows = [c["row_index"] for c in cells if c["column_index"] == cell["column_index"]
                            and table_cell_scalar(c.get("text", "")) is not None]
            boundary = min(numeric_rows) if numeric_rows else cell["row_index"]
            headers = [h for h in cells if h["row_index"] < boundary and header_applies(h, cell)]
            if not any(_family(h.get("text", "")) == family for h in headers):
                continue
            candidates.append((source, cell, headers, ev))
        if len({(s["block_id"], c["cell_id"]) for s, c, _, _ in candidates}) != 1:
            if not candidates:
                _repair_prose_unit(record, sources, family, path, changes)
            continue
        source, cell, headers, ev = candidates[0]
        row = (ev.get("table_locator") or {}).get("row_label", "")
        table = {"table_id": source["block_id"], "page": source["page"], "bbox": source.get("bbox")}
        proof = [evidence(table, h, row_label="source header", column_label=h["text"]) for h in headers if plain(h.get("text"))]
        context = None
        # Deepest explicit unit wins; parent treatment temperature is NOT the
        # enthalpy unit. Conflicting units at the same depth cause abstention.
        target = _source_header_unit(headers, source.get("caption", ""), family)
        if target:
            compatible = target in ({"mJ/mg", "J/g", "kJ/kg", "J/mol", "kJ/mol"} if family == "enthalpy" else {"°C", "K"})
            # A correct normalized field must not hide a corrupted raw unit:
            # lossless serializers and reviewers correctly read the raw first.
            current = record.get("unit_raw") or record.get("unit_normalized") or (parent or {}).get("unit_raw") or (parent or {}).get("unit_normalized")
            if compatible and canonical_unit(current) != target:
                context = _context(record)
                context["other_conditions"]["precision_original_unit"] = str(current or "")
                record["unit_raw"] = target
                record["unit_normalized"] = target
                context["other_conditions"]["source_property_unit"] = target
                context["other_condition_evidence"]["source_property_unit"] = proof
                if not any(_printed_unit(h["text"]) for h in headers):
                    context["other_condition_evidence"]["source_property_unit"] = [{
                        "block_id": source["block_id"], "page": source["page"], "bbox": source.get("bbox"),
                        "source_type": "table", "source_sentence": source["caption"], "table_locator": None}]
                changes.append({"path": path, "cell_id": cell["cell_id"], "kind": "unit", "before": current, "after": target})
        gas_headers = []
        for h in headers:
            text = plain(h["text"])
            match = re.search(r"\bin\s+(N\s*_?\s*2|air|nitrogen|argon|Ar)\b", text, re.I)
            bare = re.fullmatch(r"N\s*_?\s*2|air|nitrogen|argon|Ar", text, re.I)
            if match or bare:
                gas_headers.append((h, match[1] if match else bare[0]))
        if len({g for _, g in gas_headers}) == 1:
            gas = gas_headers[0][1]
            context = context or _context(record)
            if "source_table_atmosphere" not in context["other_conditions"]:
                context["other_conditions"]["source_table_atmosphere"] = gas
                context["other_condition_evidence"]["source_table_atmosphere"] = [
                    evidence(table, h, row_label="source atmosphere", column_label=h["text"]) for h, _ in gas_headers]
                changes.append({"path": path, "cell_id": cell["cell_id"], "kind": "atmosphere", "after": gas})
        state_headers = [h for h in headers if re.fullmatch(r"at\s+[−+-]?\d+(?:\.\d+)?\s*°\s*C", plain(h["text"]), re.I)]
        if state_headers:
            states = {plain(h["text"]) for h in state_headers}
            if len(states) == 1:
                state = next(iter(states))
                context = context or _context(record)
                prior = context["other_conditions"].get("source_table_state")
                if prior and prior != state:
                    conflicts.append({"path": path, "kind": "conflicting_state", "before": prior, "source": state})
                elif not prior:
                    context["other_conditions"]["source_table_state"] = state
                    context["other_condition_evidence"]["source_table_state"] = [
                        evidence(table, h, row_label="source state", column_label=h["text"]) for h in state_headers]
                    # Caption explains whether this is treatment or measurement;
                    # do NOT blindly assign measurement_context.temperature.
                    if source.get("caption"):
                        context["other_conditions"]["source_table_state_caption"] = source["caption"]
                        context["other_condition_evidence"]["source_table_state_caption"] = [{
                            "block_id": source["block_id"], "page": source["page"], "bbox": source.get("bbox"),
                            "source_type": "table", "source_sentence": source["caption"], "table_locator": None}]
                    changes.append({"path": path, "cell_id": cell["cell_id"], "kind": "state", "after": state})
        # A condition-specific table cannot be reconciled with unqualified
        # prose without explicitly resolving its specimen state.
        witnesses = [] if state_headers else _sign_witnesses(stage0, row, family, value)
        if witnesses:
            # Multiple opposite-sign assignments or mention of several
            # explicit specimens are not grounds for replacing a value.
            unique = {(b["block_id"], literal, number) for b, literal, number in witnesses}
            if len(unique) != 1:
                conflicts.append({"path": path, "kind": "ambiguous_sign_witness"})
                continue
            block, literal, number = witnesses[0]
            context = context or _context(record)
            context["other_conditions"]["precision_original_cell_value"] = str(record["value_raw"])
            context["other_conditions"]["source_sign_resolution"] = "explicit named prose assignment contradicts OCR table sign"
            record["value_raw"], record["value_min"], record["value_max"] = literal, number, number
            if "source_type" in record:
                record["source_type"] = "text"
            record["evidence"] = [{"block_id": block["block_id"], "page": block["page"], "bbox": block.get("bbox"),
                                   "source_type": "text", "source_sentence": block["text"], "table_locator": None}]
            changes.append({"path": path, "cell_id": cell["cell_id"], "kind": "sign", "before": value,
                            "after": number, "source_block_id": block["block_id"], "source_literal": literal})
    # Collapse only semantically identical scalar copies at exactly the same
    # physical source cell. Different samples, methods, conditions or values
    # never share this signature. Scalar/series cross-container consolidation
    # requires graph-aware remapping and is deliberately not guessed here.
    duplicates = []
    for container in ("properties", "specialized_property_observations"):
        if not merge_duplicates:
            continue
        kept, known = [], {}
        for record in output.get(container) or []:
            cells = sorted({(e.get("block_id"), (e.get("table_locator") or {}).get("cell_id"))
                            for e in record.get("evidence") or [] if (e.get("table_locator") or {}).get("cell_id")})
            if len(cells) != 1:
                kept.append(record)
                continue
            semantic = {k: v for k, v in record.items() if k not in {"property_id", "evidence", "confidence"}}
            key = json.dumps([cells, semantic], sort_keys=True, ensure_ascii=False)
            prior = known.get(key)
            if prior is None:
                kept.append(record)
                known[key] = record
                continue
            for ev in record.get("evidence") or []:
                if ev not in prior["evidence"]:
                    prior["evidence"].append(ev)
            duplicates.append({"container": container, "retained_id": prior.get("property_id"),
                               "merged_id": record.get("property_id"), "cell_id": cells[0][1]})
        if container in output:
            output[container] = kept
    return output, {"version": VERSION, "changes": changes, "conflicts": conflicts,
                    "exact_duplicates_merged": duplicates, "gold_access": False}

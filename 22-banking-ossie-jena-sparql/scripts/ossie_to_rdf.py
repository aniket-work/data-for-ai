#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Convert the Apache OSSIE ontology + demo CSVs into Turtle for Apache Jena Fuseki.

TBox (classes, subclass axioms, properties) from ``ossie/ontology.yaml``; ABox
(individuals) from the ``rdf_abox`` binding in ``rdf/abox_binding.yaml`` applied to
``data/*.csv``. Does not invent concepts missing from the OSSIE package.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_CONCEPTS = frozenset(
    {
        "Customer",
        "BankAccount",
        "BeneficialOwner",
        "RelatedParty",
        "FinancialInstitution",
        "SuspiciousActivity",
    }
)

BUILTIN = frozenset({"String", "Float", "Integer", "Boolean", "Date", "DateTime", "Decimal"})


def _slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name)


def _load_yaml(path: Path) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"expected mapping in {path}")
    return doc


def _concept_iri(ns: Namespace, concept: str, declared: str | None) -> URIRef:
    if declared and str(declared).startswith("http"):
        return URIRef(str(declared))
    if declared and ":" in str(declared):
        # keep the local name as a fragment in the single demo namespace
        local = str(declared).split(":", 1)[-1]
        return ns[_slug(local)]
    return ns[_slug(concept)]


def build_tbox(g: Graph, onto: dict[str, Any], ns: Namespace) -> dict[str, URIRef]:
    """Emit owl:Class / properties from OSSIE ontology components."""
    classes: dict[str, URIRef] = {}
    components = [c for c in (onto.get("ontology") or []) if isinstance(c, dict)]
    for comp in components:
        name = str(comp.get("concept") or "")
        if not name or name in BUILTIN:
            continue
        iri = _concept_iri(ns, name, comp.get("iri") if isinstance(comp.get("iri"), str) else None)
        classes[name] = iri
        g.add((iri, RDF.type, OWL.Class))
        g.add((iri, RDFS.label, Literal(name)))
        if comp.get("description"):
            g.add((iri, RDFS.comment, Literal(str(comp["description"]))))
        for parent in comp.get("extends") or []:
            if isinstance(parent, str) and parent:
                # parent may be resolved in a second pass
                g.add((iri, RDFS.subClassOf, ns[_slug(parent)]))

    # Second pass: fix extends targets to class IRIs when known
    for comp in components:
        name = str(comp.get("concept") or "")
        child = classes.get(name)
        if child is None:
            continue
        for parent in comp.get("extends") or []:
            if not isinstance(parent, str):
                continue
            parent_iri = classes.get(parent, ns[_slug(parent)])
            # remove provisional and re-add canonical
            provisional = ns[_slug(parent)]
            g.remove((child, RDFS.subClassOf, provisional))
            g.add((child, RDFS.subClassOf, parent_iri))

        for rel in comp.get("relationships") or []:
            if not isinstance(rel, dict) or not rel.get("name"):
                continue
            rname = str(rel["name"])
            roles = rel.get("roles") or []
            role_concept = None
            if roles and isinstance(roles[0], dict):
                role_concept = roles[0].get("concept")
            prop = ns[_slug(f"{name}_{rname}")]
            if role_concept in BUILTIN or role_concept is None:
                g.add((prop, RDF.type, OWL.DatatypeProperty))
                if role_concept == "Float":
                    g.add((prop, RDFS.range, XSD.double))
                elif role_concept == "Integer":
                    g.add((prop, RDFS.range, XSD.integer))
                elif role_concept == "Boolean":
                    g.add((prop, RDFS.range, XSD.boolean))
                elif role_concept in {"Date", "DateTime"}:
                    g.add((prop, RDFS.range, XSD.date if role_concept == "Date" else XSD.dateTime))
                else:
                    g.add((prop, RDFS.range, XSD.string))
            else:
                g.add((prop, RDF.type, OWL.ObjectProperty))
                rng = classes.get(str(role_concept), ns[_slug(str(role_concept))])
                g.add((prop, RDFS.range, rng))
            g.add((prop, RDFS.domain, child))
            g.add((prop, RDFS.label, Literal(rname)))
            if rel.get("description"):
                g.add((prop, RDFS.comment, Literal(str(rel["description"]))))

    return classes


def _cell(row: dict[str, str], column: str) -> str:
    return (row.get(column) or "").strip()


def _literal(value: str, column_hint: str = "") -> Literal:
    low = value.lower()
    if low in {"true", "false"} and (
        "flag" in column_hint or column_hint.endswith("_flag") or column_hint == "npl_flag"
    ):
        return Literal(low == "true", datatype=XSD.boolean)
    try:
        if "." in value:
            return Literal(float(value), datatype=XSD.double)
        return Literal(int(value), datatype=XSD.integer)
    except ValueError:
        return Literal(value)


def build_abox(
    g: Graph,
    classes: dict[str, URIRef],
    ns: Namespace,
    abox: dict[str, Any],
    data_dir: Path,
) -> None:
    sources = abox.get("sources") or {}
    if not isinstance(sources, dict):
        raise ValueError("rdf_abox.sources must be a mapping")

    individuals: dict[tuple[str, str], URIRef] = {}

    # Pass 1: create individuals + literals
    for concept, spec in sources.items():
        if not isinstance(spec, dict):
            continue
        class_iri = classes.get(concept)
        if class_iri is None:
            raise ValueError(
                f"rdf_abox source concept {concept!r} missing from OSSIE ontology"
            )
        csv_name = spec.get("csv")
        id_col = spec.get("id_column")
        if not csv_name or not id_col:
            raise ValueError(f"rdf_abox.{concept} needs csv + id_column")
        path = data_dir / str(csv_name)
        if not path.is_file():
            raise ValueError(f"missing CSV {path}")
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rid = _cell(row, str(id_col))
                if not rid:
                    continue
                subj = ns[_slug(f"{concept}_{rid}")]
                individuals[(concept, rid)] = subj
                g.add((subj, RDF.type, class_iri))
                g.add((subj, RDFS.label, Literal(rid)))
                for prop_name, col in (spec.get("literals") or {}).items():
                    val = _cell(row, str(col))
                    if val == "":
                        continue
                    pred = ns[_slug(f"{concept}_{prop_name}")]
                    g.add((subj, pred, _literal(val, str(col))))
                for rule in spec.get("type_when") or []:
                    if not isinstance(rule, dict):
                        continue
                    extra = str(rule.get("concept") or "")
                    col = str(rule.get("column") or "")
                    equals = str(rule.get("equals") or "")
                    cell = _cell(row, col)
                    if extra and cell.lower() == equals.lower() and extra in classes:
                        g.add((subj, RDF.type, classes[extra]))

    # Pass 2: object links
    for concept, spec in sources.items():
        if not isinstance(spec, dict):
            continue
        csv_name = spec.get("csv")
        id_col = spec.get("id_column")
        path = data_dir / str(csv_name)
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rid = _cell(row, str(id_col))
                subj = individuals.get((concept, rid))
                if subj is None:
                    continue
                for prop_name, link in (spec.get("links") or {}).items():
                    if not isinstance(link, dict):
                        continue
                    col = str(link.get("column") or "")
                    target_concept = str(link.get("concept") or "")
                    tid = _cell(row, col)
                    if not tid or not target_concept:
                        continue
                    obj = individuals.get((target_concept, tid))
                    if obj is None:
                        # mint target stub if missing (should not happen when the CSV keys are consistent)
                        obj = ns[_slug(f"{target_concept}_{tid}")]
                        if target_concept in classes:
                            g.add((obj, RDF.type, classes[target_concept]))
                        individuals[(target_concept, tid)] = obj
                    pred = ns[_slug(f"{concept}_{prop_name}")]
                    g.add((subj, pred, obj))


def convert(
    ossie_dir: Path,
    data_dir: Path,
    binding_path: Path,
    out_path: Path,
) -> None:
    onto = _load_yaml(ossie_dir / "ontology.yaml")
    binding = _load_yaml(binding_path)
    abox = binding.get("rdf_abox") or {}
    if not isinstance(abox, dict) or not abox.get("sources"):
        raise ValueError("binding file missing rdf_abox.sources")

    ns_uri = str(abox.get("namespace") or "https://example.com/happn-bank#")
    if not ns_uri.endswith(("#", "/")):
        ns_uri += "#"
    ns = Namespace(ns_uri)

    names = {
        str(c.get("concept"))
        for c in (onto.get("ontology") or [])
        if isinstance(c, dict) and c.get("concept")
    }
    missing = sorted(REQUIRED_CONCEPTS - names)
    if missing:
        raise ValueError(
            "OSSIE ontology missing required graph concepts: "
            + ", ".join(missing)
            + " — fix ossie/ontology.yaml first"
        )

    g = Graph()
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)
    g.bind(str(abox.get("prefix") or "happn"), ns)

    ontology_iri = ns["HappnBankingOntology"]
    g.add((ontology_iri, RDF.type, OWL.Ontology))
    g.add((ontology_iri, RDFS.label, Literal("Happn banking ontology (from Apache OSSIE)")))

    classes = build_tbox(g, onto, ns)
    build_abox(g, classes, ns, abox, data_dir)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_path), format="turtle")
    print(f"ok  wrote {os.path.relpath(out_path)} ({len(g)} triples)")
    print(f"  classes: {len(classes)}")
    print(f"  required concepts present: {', '.join(sorted(REQUIRED_CONCEPTS))}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ossie-dir", type=Path, default=ROOT / "ossie")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--binding",
        type=Path,
        default=ROOT / "rdf" / "abox_binding.yaml",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "rdf" / "banking.ttl")
    args = parser.parse_args(argv)
    try:
        convert(args.ossie_dir, args.data_dir, args.binding, args.out)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

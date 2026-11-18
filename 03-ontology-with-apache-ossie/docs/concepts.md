# Ontology concepts in Apache Ossie (incubating)

A short guide to the parts of an Ossie ontology used in this lesson. Everything here follows the [ontology specification](https://github.com/apache/ossie/blob/main/ontology/ontology.md) at version `0.3.0.dev0` (unreleased). The specification and its JSON Schemas are the authority; this page only summarizes them.

## Three kinds of document

| Document | Describes | Schema |
|---|---|---|
| Semantic model (core spec) | Datasets, fields, relationships (joins), metrics | `core-spec/ossie-schema.json` |
| Ontology | Concepts, relationships between them, business rules | `ontology/ontology.json` |
| Mapping document | How fields of one semantic model populate one ontology | `ontology/mapping.json` |

A mapping document is recognized by having `concept_mappings`, `ontology_ref` and `semantic_model_ref`. Each reference has a `name`, which must equal the referenced document's own `name`, and an optional `iri` saying where to load it from (relative paths resolve from the mapping file's folder). The older `ontology_mappings` list inside the ontology still validates but is deprecated ([PR #458](https://github.com/apache/ossie/pull/458)).

## Ontology document

Top level: `version` (`0.3.0.dev0`), `name`, `ontology` (the list of concepts) are required. `description`, `ai_context`, `prefixes` and `requires` are optional.

### Concepts

| Field | Meaning |
|---|---|
| `concept`, `type` | Name, and `EntityType` or `ValueType` (required) |
| `extends` | Supertypes. Value types must reach a built-in (`String`, `Integer`, `Decimal`, `Float`, `Boolean`, `Date`, `DateTime`); entity types extend entity types and implicitly `Any` |
| `identify_by` | Relationships that form the preferred identifier |
| `requires`, `derived_by` | Rules that constrain, or derive, the population |
| `relationships` | Relationships where this concept plays the first role |
| `iri` | Optional global identifier: a full IRI or a `prefix:local` QName |

### Relationships

| Field | Meaning |
|---|---|
| `name` | Joined with the concept name: `Sensor.installed_at` |
| `roles` | The other roles, in order. Each has a `concept` and an optional `name` (needed when a concept plays two roles) |
| `multiplicity` | `ManyToOne` (last role determined by the others) or `OneToOne` (binary only, many-to-one both ways) |
| `verbalizes` | Required sentence patterns, e.g. `{Sensor} is installed at {Site}`; roles with names are written `{Sensor:primary}` |
| `requires`, `derived_by` | Rules over the relationship's links |
| `iri` | Optional global identifier |

Relationships have set semantics, and their links never contain nulls. A relationship with no extra roles is unary, e.g. `{Item} is actively sold`.

### Business rules

Expressions use the Ossie [expression language](https://github.com/apache/ossie/blob/main/core-spec/expression_language.md) with dot-joins over relationships. In this lesson:

```yaml
- concept: Celsius
  requires: [Celsius >= -60, Celsius <= 80]               # value range
- name: backup_for
  requires: ['Sensor.installed_at == primary.installed_at']   # same site as the primary
- name: monitored_for
  derived_by: ['Sensor.installed_at.owned_by(Customer)']  # derived by navigation
- concept: AlertReading
  extends: [SensorReading]
  derived_by: ["SensorReading.status == 'ALERT'"]         # derived subtype
```

### IRIs and prefixes

```yaml
prefixes:
  sosa: http://www.w3.org/ns/sosa/
ontology:
- concept: Sensor
  iri: sosa:Sensor        # expands to http://www.w3.org/ns/sosa/Sensor
```

A QName whose prefix is not declared is invalid. IRIs do not change how concepts are referenced inside the ontology; expressions, roles and mappings keep using local names.

## Mapping document

| Construct | Use |
|---|---|
| `object_mappings` | An `expression` (`devices.device_id`) for a simple identifier, or `referent_mappings` for a compound one |
| `referent_mappings` | One per identifying relationship; nest them when the identifier is itself an entity (`sensor` then `id`) |
| `link_mappings` | A tree. The root `object_mapping` selects the objects; each child names a `relationship` and maps its last role. A child's depth equals the relationship's arity |

The official validator (`validation/validate.py --schema ontology/mapping.json`) loads the referenced ontology and semantic model and checks that every concept, relationship and `dataset.field` named in the mapping exists.

"""Shared domain configuration for maintained graph-source implementations."""

from __future__ import annotations

REACTOME_ALLOWED_NODE_ENTITY_TYPES = (
    "Chemical",
    "Protein",
    "Entity",
    "Reaction",
    "Gene",
    "Compound",
    "Species",
    "Study",
    "Pathway",
    "Phenotype",
    "Anatomy",
    "Lab Strain",
    "Note",
    "Cause",
    "Observation",
    "Association",
    "Effect",
    "Correlation",
    "Map",
    "Link",
    "Lab Sample",
    "Food",
    "Phenomena",
    "Company",
    "Mutation",
)

REACTOME_TRACE_RELATIONSHIP_TYPES = (
    "activeUnitOf",
    "candidateOf",
    "catalystOf",
    "catalyzes",
    "componentOf",
    "input",
    "memberOf",
    "output",
    "regulates",
    "regulatorOf",
    "repeatedUnitOf",
    "requiredInput",
)

REACTOME_TRACE_RELATIONSHIP_TYPES_WITH_REF = (
    *REACTOME_TRACE_RELATIONSHIP_TYPES,
    "referenceEntity",
)

REACTOME_CURRENCY_METABOLITE_LABEL = "CurrencyMetabolite"
REACTOME_DEFAULT_EXCLUDED_NODE_LABELS = (REACTOME_CURRENCY_METABOLITE_LABEL,)

REACTOME_EDGE_DESC_DICT = {
    "activeUnitOf": "is active unit of",
    "candidateOf": "is candidate of",
    "catalystOf": "is catalyst of",
    "catalyzes": "catalyzes",
    "componentOf": "is component of",
    "hasComponent": "has component",
    "input": "is consumed by",
    "memberOf": "is member of",
    "output": "produces",
    "referenceEntity": "has reference entity",
    "regulates": "regulates",
    "regulatorOf": "is regulator of",
    "repeatedUnitOf": "is repeated unit of",
    "requiredInput": "is required input for",
}

BIOCYC_CURRENCY_METABOLITE_LABEL = "CurrencyMetabolite"
BIOCYC_DEFAULT_EXCLUDED_NODE_LABELS = (BIOCYC_CURRENCY_METABOLITE_LABEL,)

BIOCYC_EDGE_DESC_DICT = {
    "ELEMENT_OF": "is element of",
    "ENCODES": "encodes",
    "MODIFIED_TO": "is modified to",
    "COMPONENT_OF": "is component of",
    "CONSUMED_BY": "is consumed by",
    "PRODUCES": "produces",
    "IN_PATHWAY": "is in",
    "CATALYZES": "catalyzes",
    "REGULATES": "regulates",
    "HAS_GENE": "contains",
    "ACTIVATES": "activates",
    "INHIBITS": "inhibits",
}


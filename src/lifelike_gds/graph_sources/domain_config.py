"""Shared domain configuration for maintained graph-source implementations."""

from __future__ import annotations

REACTOME_TRACE_RELATIONSHIP_TYPES = (
  'activeUnitOf',
  'candidateOf',
  'catalystOf',
  'catalyzes',
  'componentOf',
  'eventOf',
  'inputOf',
  'memberOf',
  'output',
  'precedesEvent',
  'regulates',
  'regulatorOf',
  'repeatedUnitOf',
  'requiredInputOf'
)
REACTOME_REFERENCE_REL_TYPE = "refersToPhysicalEntity"

REACTOME_TRACE_NODE_LABEL = "HumanTrace"
REACTOME_EXCLUDED_NODE_LABELS = ['TraceCurrency', 'TraceHub']

REACTOME_EDGE_DESC_DICT = {
    "activeUnitOf": "is active unit of",
    "candidateOf": "is candidate of",
    "catalystOf": "is catalyst of",
    "catalyzes": "catalyzes",
    "componentOf": "is component of",
    "hasComponent": "has component",
    "inputOf": "is consumed by",
    "memberOf": "is member of",
    "output": "produces",
    "precedesEvent": "precedes",
    "referenceEntity": "has reference entity",
    "regulates": "regulates",
    "regulatorOf": "is regulator of",
    "repeatedUnitOf": "is repeated unit of",
    "requiredInputOf": "is required input for",
}


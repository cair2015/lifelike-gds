# Reactome Neo4j Database Setup for Radiate Analysis and Traces

This document describes the Cypher queries used to configure the Neo4j database for performing Radiate analysis and network trace operations on Reactome data.

## Overview

The database setup process involves several key steps:
1. **Species Filtering**: Isolate human-specific biological data
2. **Node Labeling**: Classify nodes with semantic labels for analysis
3. **Relationship Normalization**: Create reverse relationships for bidirectional graph navigation
4. **Trace Configuration**: Define currency chemicals and hub entities
5. **Graph Projection**: Create an analysis-ready subgraph

---

## Step 1: Species Filtering

### Remove Non-Human Events and Physical Entities

```cypher
CALL apoc.periodic.iterate(
  "MATCH (n:Event)
   WHERE n.speciesName IS NOT NULL
     AND n.speciesName <> 'Homo sapiens'
   RETURN id(n) AS id",
  "MATCH (n) WHERE id(n) = id DETACH DELETE n",
  {batchSize: 2000, parallel: false}
);

CALL apoc.periodic.iterate(
  "MATCH (n:PhysicalEntity)
   WHERE n.speciesName IS NOT NULL
     AND n.speciesName <> 'Homo sapiens'
   RETURN id(n) AS id",
  "MATCH (n) WHERE id(n) = id DETACH DELETE n",
  {batchSize: 2000, parallel: false}
);
```

**Purpose**: Remove all non-human biological events and physical entities from the database. Uses `apoc.periodic.iterate` for efficient batch deletion (2000 nodes per batch) without overwhelming the database.

---

## Step 2: Initial Node Classification

### Label Human-Related Nodes

```cypher
match(n:Event) SET n:HumanTrace
match(n:PhysicalEntity) SET n:HumanTrace;

match(n:ReferenceGeneProduct)-[:species]->(s:Species {taxId: '9606'}) 
SET n:HumanTrace;

MATCH (n:ReferenceDNASequence)-[:referenceGene]-(m:ReferenceGeneProduct) SET n:Gene;

MATCH (n:ReferenceGeneProduct) where n.databaseName='UniProt' SET n:Protein;
MATCH (n:ReferenceMolecule) SET n:Chemical;
```

**Purpose**:
- Mark all Events and PhysicalEntities as `HumanTrace` for subsequent filtering
- Label ReferenceGeneProducts connected to human species (NCBI taxId 9606) as `HumanTrace`
- Classify ReferenceDNASequences as `Gene`
- Classify UniProt ReferenceGeneProducts as `Protein`
- Classify ReferenceMolecules as `Chemical`

---

## Step 3: Relationship Quality Check and Expansion

### Identify and Propagate Human Trace Label

```cypher
// Check non-HumanTrace nodes connected to Events
MATCH(n:Event)-[:input|requiredInputComponent|output|catalystActivity|regulatedBy]-(m) 
where not m:HumanTrace return labels(m), count(*)

// Propagate HumanTrace label to connected entities
MATCH(n:Event)-[:input|requiredInputComponent|output|catalystActivity|regulatedBy]-(m) 
where not m:HumanTrace 
SET m:HumanTrace

// Clean up orphaned entities
match(n:CatalystActivity) where not n:HumanTrace DETACH DELETE n;
MATCH (n:Regulation) where not n:HumanTrace DETACH DELETE n; 

// Verify no orphaned entities remain
MATCH(n:Event)--(m:PhysicalEntity) where not m:HumanTrace return count(*)

// Verify all container components are marked for tracing
// return 0 - all sub member of components are also marked for tracing
match(n:PhysicalEntity:HumanTrace)-[:hasComponent|hasMember|hasCandidate*]->(m) where not m:HumanTrace return count(*)
```

**Purpose**:
- Find any nodes connected to Events through key relationships that aren't yet marked as `HumanTrace`
- Propagate the `HumanTrace` label to ensure all relevant connected entities are included
- Remove CatalystActivity and Regulation nodes that aren't marked as `HumanTrace` (likely orphaned)
- Verify that no untraced physical entities are still connected to Events
- Check container tracing by verifying that all components, members, and candidates nested within `HumanTrace` physical entities are also marked as `HumanTrace`. This uses variable-length paths (`*`) to check all levels of composition hierarchy.

---

## Step 4: Create Reverse Relationships

### Bidirectional Graph Navigation

```cypher
// Complex-Component relationships
match(n:Complex)-[:hasComponent]->(m) 
MERGE (m)-[:componentOf]->(n);

// Set memberships
MATCH (n:EntitySet)-[:hasMember]->(m)
MERGE (m)-[:memberOf]->(n);

MATCH (n:CandidateSet)-[:hasCandidate]->(m)
MERGE (m)-[:candidateOf]->(n);

// Polymer units
MATCH (n:Polymer)-[:repeatedUnit]->(m)
MERGE (m)-[:repeatedUnitOf]->(n);

// Event inputs and components
MATCH (n:Event)-[:input]->(m)
MERGE (m)-[:inputOf]->(n);

MATCH (n:Event)-[:requiredInputComponent]->(m)
MERGE (m)-[:requiredInputOf]->(n);

// Catalyst relationships
MATCH (n:Event)-[:catalystActivity]->(m:CatalystActivity) 
MERGE (m)-[:catalyzes]->(n);

MATCH (n:CatalystActivity)-[:physicalEntity]->(m) 
MERGE (m)-[:catalystOf]->(n);

MATCH (n:CatalystActivity)-[:activeUnit]->(m:PhysicalEntity) 
MERGE (m)-[:activeUnitOf]->(n);

// Regulation relationships
MATCH (n:Event)-[:regulatedBy]->(m:Regulation) 
MERGE (m)-[:regulates]->(n);

MATCH (n:Regulation)-[:regulator]->(m) 
MERGE (m)-[:regulatorOf]->(n);

MATCH (n:Regulation)-[:activeUnit]->(m)
MERGE (m)-[:activeUnitOf]->(n);

// Event precedence
MATCH (downstream:Event)-[:precedingEvent]->(upstream) 
MERGE (upstream)-[:precedesEvent]->(downstream);

// Pathway events
MATCH (n:Pathway)-[:hasEvent]->(m) 
MERGE (m)-[:eventOf]->(n);

// Reference entity mappings
MATCH (n:PhysicalEntity:HumanTrace)-[:referenceEntity]->(m:ReferenceGeneProduct) 
MERGE (m)-[:refersToPhysicalEntity]->(n);

MATCH (n:PhysicalEntity:HumanTrace)-[:referenceEntity]->(m:ReferenceMolecule) 
MERGE (m)-[:refersToPhysicalEntity]->(n);
```

**Purpose**: Create inverse relationships for all major edge types. This enables algorithms to traverse the graph in both directions, essential for:
- Upstream/downstream event tracing
- Bidirectional pathway analysis
- Complete neighborhood exploration during graph algorithms

---

## Step 5: Define Trace Metadata

### Trace Currency Chemicals

```cypher
:param TRACE_CURRENCY_CHEMS => [
  "3',5'-ADP",
  "ADP",
  "AMP",
  "ATP",
  "CO",
  "CO2",
  "Ca2+",
  "Cl-",
  "CoA-SH",
  "FAD",
  "FADH2",
  "GMP",
  "GDP",
  "GTP",
  "H+",
  "H2O",
  "H2O2",
  "HCO3-",
  "K+",
  "NAD(P)+",
  "NAD(P)H",
  "NAD+",
  "NADH",
  "NADP+",
  "NADPH",
  "NH3",
  "NH4+",
  "Na+",
  "O2",
  "O2.-",
  "PAP",
  "PPi",
  "PPi(3-)",
  "Pi",
  "UDP",
  "adenosine 5'-monophosphate",
  "phosphate"
];
```

**Purpose**: Define metabolic currency molecules—universal cofactors and energy molecules that appear in many reactions. These are typically excluded from primary trace paths to focus on substrate-specific analysis.

### Trace Hub Entities

```cypher
:param TRACE_HUB_ENTITIES => [
  "Ub"
];
```

**Purpose**: Define highly connected hub molecules (ubiquitin in this case) that frequently appear as intermediaries. Marking these separately allows for selective inclusion/exclusion in path analysis.

### Label Currency and Hub Chemicals

```cypher
UNWIND $TRACE_CURRENCY_CHEMS AS chem
OPTIONAL MATCH (n:PhysicalEntity)
WHERE chem in n.name
SET n:TraceCurrency;

UNWIND $TRACE_HUB_ENTITIES AS chem
OPTIONAL MATCH (n:PhysicalEntity)
WHERE chem in n.name
SET n:TraceHub;
```

**Purpose**: Search all physical entities by name against the currency and hub lists, then apply appropriate labels for filtering during trace operations.

### Verify Connectivity

```cypher
MATCH (n:TraceCurrency)
WITH n, count{(n)--()} AS degree
return n.displayName, degree
order by degree desc;

MATCH (n:TraceHub)
WITH n, count{(n)--()} AS degree
return n.displayName, degree
order by degree desc;
```

**Purpose**: Analyze the degree (connectivity) of currency and hub entities to verify their importance in the network. High-degree nodes confirm they should be treated as special entities during analysis.

---

## Step 6: Clean Up Base Labels

```cypher
MATCH (n:HumanTrace) REMOVE n:BaseObject, n:Trackable, n:Deletable;
```

**Purpose**: Remove internal Neo4j infrastructure labels from human trace nodes to clean up the schema and reduce label complexity.

---

## Step 7: Set Entity Types

### Classify Node Types for Analysis and Visualization

```cypher
// Classify nodes based on their reference entities
match(n:HumanTrace:PhysicalEntity)-[:referenceEntity]->(:Protein) SET n.entityType = 'Protein';

match(n:HumanTrace:PhysicalEntity)-[:referenceEntity]->(:Chemical) SET n.entityType = 'Chemical';

match(n:HumanTrace:PhysicalEntity)-[:referenceEntity]->(:Gene) where n.entityType is null SET n.entityType = 'Gene';

match(n:PhysicalEntity:HumanTrace)-[:referenceEntity]->(r:ReferenceRNASequence) where n.entityType is null SET n.entityType = 'RNA';

match(n:PhysicalEntity:HumanTrace)-[:referenceEntity]->(r:ReferenceDNASequence) where n.entityType is null SET n.entityType = 'Gene';

// Fallback: use schemaClass for nodes without determined entityType, including events
match(n:HumanTrace) where n.entityType is null SET n.entityType = n.schemaClass;
```

**Purpose**: Populate the `entityType` property on all `HumanTrace` nodes with standardized classification values:
- **Protein**: Physical entities referencing gene products with UniProt identifiers
- **Chemical**: Physical entities referencing chemical molecules
- **Gene**: Physical entities referencing DNA sequences or genes
- **RNA**: Physical entities referencing RNA sequences
- **Event type**: For nodes without reference entities, fallback to the original `schemaClass` property (Reaction, Complex, etc.)

The `entityType` property is used throughout the analysis pipeline for:
- Display and visualization in network diagrams
- Node filtering and grouping in radiate analysis
- Report generation and data export
- Type-specific trace algorithms

This approach ensures all nodes have meaningful type information while maintaining backward compatibility with the Reactome schema.

---

## Step 8: Create Analysis Graph Projection

### Final Graph Projection for Radiate and Trace Operations

```cypher
MATCH (a:HumanTrace)-[r]->(b:HumanTrace)
WHERE not a:TraceCurrency and not b:TraceCurrency
and not a:TraceHub and not b:TraceHub and 
 type(r) IN [
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
]
RETURN
  elementId(a) AS source,
  elementId(b) AS target,
  type(r) AS relationship_type,
  elementId(r) AS relationship_id
```

**Purpose**: Create a final subgraph containing:
- Only nodes marked as `HumanTrace`
- **Excludes TraceCurrency chemicals and TraceHub entities** from both source and target nodes, preventing universal cofactors and hub molecules from being included as endpoints
- Only relationships of types relevant to biological pathway analysis
- Returns structured output with element IDs for source and target nodes, relationship types, and relationship IDs

This filtered graph is optimized for:
  - Shortest path algorithms
  - Radiate trace operations
  - Efficient network neighborhood searches
  - Focused analysis without universal metabolites cluttering the results

The included relationship types represent:
- **Structural relationships**: componentOf, memberOf, repeatedUnitOf, candidateOf, activeUnitOf
- **Functional relationships**: catalyzes/catalystOf, regulates/regulatorOf, inputOf/requiredInputOf
- **Hierarchical relationships**: eventOf, precedesEvent, output

---

## Summary

This database setup creates an optimized, filtered Neo4j graph that:

1. **Focuses on human biology** by removing non-human species data
2. **Provides rich semantic classification** with node type labels
3. **Enables bidirectional traversal** through reverse relationships
4. **Identifies special entities** (currency chemicals, hubs) for smart filtering
5. **Maintains clean schema** by removing infrastructure labels
6. **Classifies node types** with standardized `entityType` property for analysis and visualization
7. **Provides analysis-ready projection** containing only relevant nodes and relationships

The result is a clean, semantically-rich graph suitable for complex network analysis operations like Radiate tracing and shortest path queries.

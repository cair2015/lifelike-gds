# Build Reactome GraphDB for GDS

## Overview

This document provides instructions for building and optimizing a Reactome GraphDB instance compatible with Neo4j Graph Data Science (GDS) analytics. The process involves downloading the Reactome dump file, migrating it from older Neo4j versions if needed, configuring memory settings, and performing data cleanup and restructuring to optimize the graph for analysis.

**Reactome Version:** 95 (or latest available)

---

## Step 1: Download Reactome Dump File

Download the official Reactome GraphDB dump file:

```bash
wget -c https://download.reactome.org/95/reactome.graphdb.dump
```

---

## Step 2: Create Neo4j Instance and Load Dump File

### Handling Version Compatibility

The Reactome dump file may be in an older Neo4j format (v4.x) and requires migration to work with Neo4j 5.x or later. Follow these steps:

#### Step 2.1: Create a Neo4j 5.x Instance

Create a new Neo4j instance using version 5.x or later in Neo4j Desktop or your preferred environment.

#### Step 2.2: Copy and Rename the Dump File

Copy the downloaded dump file to the instance's `dumps` folder and rename it to `neo4j.dump`:

```bash
cp reactome.graphdb.dump <neo4j-instance-path>/dumps/neo4j.dump
```

#### Step 2.3: Load the Dump File

Use the `neo4j-admin` command to load the dump:

```bash
bin/neo4j-admin database load --from-path=dumps neo4j --overwrite-destination=true
```

#### Step 2.4: Run Database Migration

Migrate the database to the new format, converting legacy B-tree indexes to range indexes:

```bash
bin/neo4j-admin database migrate neo4j --force-btree-indexes-to-range
```

#### Step 2.5: Export Data from Neo4j 5.x

Dump the migrated database for use in later versions:

```bash
bin/neo4j-admin database dump neo4j --to-path=backups
```

This creates a `neo4j.dump` file that can be imported directly into Neo4j 5.x or later versions.

#### Step 2.6: Load into Final Neo4j Instance

Use the migrated dump file to create your production Reactome-GDS instance. Neo4j versions 5.x and later can import this dump file directly.

---

## Step 3: Configure Memory Settings

### Determine Optimal Memory Configuration

Before running any analysis, configure Neo4j's heap and page cache settings to prevent out-of-memory errors:

```bash
bin/neo4j-admin server memory-recommendation
```

This command analyzes your system and recommends appropriate settings.

### Apply Memory Configuration

Edit `neo4j.conf` and set the recommended values. Example configuration:

```properties
server.memory.heap.initial_size=5g
server.memory.heap.max_size=5g
server.memory.pagecache.size=7g
```

Adjust these values based on your system's available memory and the memory-recommendation output.

---

## Step 4: Clean and Optimize Graph Database

The Reactome database contains extensive metadata and relationships that are not needed for GDS analytics. The following sections describe how to clean and optimize the graph through a series of changelog operations.

### Changelog-0000: Initial Data Cleanup

This changeset removes unnecessary metadata nodes and relationships, filters for human-only data, and restructures properties for better graph traversal.

#### 4.1: Remove DatabaseObject Labels

The `DatabaseObject` label provides no analytical value. Remove it from all nodes:

```cypher
MATCH (n:DatabaseObject)
CALL (n) {
  REMOVE n:DatabaseObject
} IN TRANSACTIONS OF 1000 ROWS
```

**Alternative method using APOC** (if periodic iteration is preferred):

```cypher
CALL apoc.periodic.iterate(
  "MATCH (n:DatabaseObject) RETURN n",
  "REMOVE n:DatabaseObject",
  {batchSize: 1000, parallel: false}
)
```

#### 4.2: Remove Provenance Nodes

Remove metadata nodes related to data provenance and curation (InstanceEdit, Affiliation, Person, Publication):

```cypher
MATCH (n:InstanceEdit) DETACH DELETE n;
MATCH (n:Affiliation) DETACH DELETE n;
MATCH (n:Person) DETACH DELETE n;
MATCH (n:Publication) DETACH DELETE n;
```

**Note:** These removal operations are sequential. Consider batching if your database is large:

```cypher
CALL apoc.periodic.iterate(
  "MATCH (n:InstanceEdit) RETURN id(n) AS id",
  "MATCH (n) WHERE id(n) = id DETACH DELETE n",
  {batchSize: 2000}
)
```

#### 4.3: Filter for Human-Only Pathway Data

Remove all non-human entities since analysis focuses exclusively on human pathways:

```cypher
MATCH (n:Taxon) DETACH DELETE n;
MATCH (n:Event) WHERE n.speciesName <> 'Homo sapiens' DETACH DELETE n;
MATCH (n:PhysicalEntity) WHERE (n.speciesName IS NOT NULL) AND n.speciesName <> 'Homo sapiens' DETACH DELETE n;
```

**For large datasets, use batched deletion:**

```cypher
CALL apoc.periodic.iterate(
  "MATCH (n:PhysicalEntity) WHERE n.speciesName IS NOT NULL AND n.speciesName <> 'Homo sapiens' RETURN id(n) AS id",
  "MATCH (n) WHERE id(n) = id DETACH DELETE n",
  {batchSize: 2000}
)
```

#### 4.4: Restructure Entity Properties

Standardize naming and extract compartment information:

```cypher
-- Set commonName from the first name entry
MATCH (n:PhysicalEntity) SET n.commonName = n.name[0];

-- Convert compartment relationships to a property array
MATCH (n:PhysicalEntity)-[r:compartment]-(x)
WITH n, COLLECT(DISTINCT x.name) AS compartments, COLLECT(r) AS rels
SET n.compartment = compartments
FOREACH (rel IN rels | DELETE rel);

-- Apply same restructuring to Events
MATCH (n:Event)-[r:compartment]-(x)
WITH n, COLLECT(DISTINCT x.name) AS compartments, COLLECT(r) AS rels
SET n.compartment = compartments
FOREACH (rel IN rels | DELETE rel);
```

#### 4.5: Reverse and Rename Relationships

Restructure relationships to improve traversal efficiency and semantic clarity. Reverse directional relationships and standardize naming:

```cypher
-- Component relationships: Complex -> Component becomes Component <- Complex
MATCH (n:Complex)-[r:hasComponent]->(x) 
MERGE (x)-[:componentOf]->(n) 
DELETE r;

-- Member relationships: EntitySet -> Member becomes Member <- EntitySet
MATCH (n:EntitySet)-[r:hasMember]->(x) 
MERGE (x)-[:memberOf]->(n) 
DELETE r;

-- Catalyst relationships: Reaction -> Catalyst becomes Catalyst <- Reaction
MATCH (n:ReactionLikeEvent)-[r:catalystActivity]->(x) 
MERGE (x)-[:catalyzes]->(n) 
DELETE r;

-- CatalystActivity relationships
MATCH (n:CatalystActivity)-[r:physicalEntity]->(x) 
MERGE (x)-[:catalystOf]->(n) 
DELETE r;

MATCH (n:CatalystActivity)-[r:activeUnit]->(x) 
MERGE (x)-[:activeUnitOf]->(n) 
DELETE r;

-- Regulation relationships: Entity -> Regulation becomes Regulation <- Entity
MATCH (n)-[r:regulatedBy]->(x:Regulation) 
MERGE (x)-[:regulates]->(n) 
DELETE r;

-- Regulator relationships: Regulation -> Regulator becomes Regulator <- Regulation
MATCH (n:Regulation)-[r:regulator]->(x) 
MERGE (x)-[:regulatorOf]->(n) 
DELETE r;

-- Regulation active unit relationships
MATCH (n:Regulation)-[r:activeUnit]->(x) 
MERGE (x)-[:activeUnitOf]->(n) 
DELETE r;

-- Candidate relationships
MATCH (n)-[r:hasCandidate]->(x) 
MERGE (x)-[:candidateOf]->(n) 
DELETE r;

-- Required input relationships
MATCH (n)-[r:requiredInputComponent]->(x) 
MERGE (x)-[:requiredInput]->(n) 
DELETE r;

-- Repeated unit relationships
MATCH (n)-[r:repeatedUnit]->(x) 
MERGE (x)-[:repeatedUnitOf]->(n) 
DELETE r;
```

---

### Changelog-0100: No Changes

This version contains no modifications. It serves as a checkpoint in the versioning chain.

---

### Changelog-0200: Add Semantic Annotations

This changeset adds synonym nodes for better entity matching and assigns standardized entity type labels for consistent analytics.

#### 4.6: Create Synonym Nodes and Relationships

Create a constraint for unique synonyms and link all entity names through `HAS_SYNONYM` relationships:

```cypher
-- Create unique constraint on Synonym names
CREATE CONSTRAINT synonym_name_unique IF NOT EXISTS
FOR (s:Synonym)
REQUIRE s.name IS UNIQUE;

-- Extract gene names as synonyms for gene products
CALL apoc.periodic.iterate(
  "
  MATCH (n:ReferenceGeneProduct)
  WHERE n.geneName IS NOT NULL
  UNWIND n.geneName AS syn
  WITH id(n) AS nid, TRIM(syn) AS syn
  WHERE syn IS NOT NULL AND syn <> ''
  RETURN DISTINCT nid, syn
  ",
  "
  MATCH (n:ReferenceGeneProduct)
  WHERE id(n) = nid
  MERGE (s:Synonym {name: syn})
  MERGE (n)-[:HAS_SYNONYM]->(s)
  ",
  {batchSize: 1000, parallel: false}
);

-- Extract all names as synonyms for physical entities
CALL apoc.periodic.iterate(
  "
  MATCH (n:PhysicalEntity)
  WHERE n.name IS NOT NULL
  UNWIND n.name AS syn
  WITH id(n) AS nid, TRIM(syn) AS syn
  WHERE syn IS NOT NULL AND syn <> ''
  RETURN DISTINCT nid, syn
  ",
  "
  MATCH (n:PhysicalEntity)
  WHERE id(n) = nid
  MERGE (s:Synonym {name: syn})
  MERGE (n)-[:HAS_SYNONYM]->(s)
  ",
  {batchSize: 1000, parallel: false}
);
```

#### 4.7: Assign Entity Type Labels

Add standardized labels and properties for entity classification:

```cypher
-- Classify molecular entities based on reference types
MATCH (n:EntityWithAccessionedSequence) 
WHERE (n)-[:referenceEntity]-(:ReferenceDNASequence) 
SET n:Gene, n.entityType = 'Gene';

MATCH (n:EntityWithAccessionedSequence) 
WHERE (n)-[:referenceEntity]-(:ReferenceRNASequence) 
SET n:RNA, n.entityType = 'RNA';

MATCH (n:EntityWithAccessionedSequence) 
WHERE (n)-[:referenceEntity]-(:ReferenceGeneProduct) 
SET n:Protein, n.entityType = 'Protein';

MATCH (n:SimpleEntity) 
SET n:Chemical, n.entityType = 'Chemical';

-- Classify reference and complex entities
MATCH (n:ReferenceGeneProduct) 
SET n.nodeLabel = 'Gene';

MATCH (n:Complex) 
SET n.entityType = 'Protein';

MATCH (n:EntitySet) 
SET n.entityType = 'EntitySet';

MATCH (n:Polymer) 
SET n.entityType = 'Polymer';

MATCH (n:ProteinDrug) 
SET n.entityType = 'Protein';

MATCH (n:ChemicalDrug) 
SET n.entityType = 'Chemical';

-- Set default type for unclassified physical entities
MATCH (n:PhysicalEntity) 
WHERE n.entityType IS NULL 
SET n.entityType = 'Entity';

-- Classify event and pathway entities
MATCH (n:ReactionLikeEvent) 
SET n.entityType = 'Reaction';

MATCH (n:CatalystActivity) 
SET n.entityType = 'CatalystActivity';

MATCH (n:Regulation) 
SET n.entityType = 'Regulation';

MATCH (n:Pathway) 
SET n.entityType = 'Pathway';
```

---

### Changelog-0300: Standardize Naming Conventions

This changeset standardizes property names and values across all entity types to match conventions used in other databases and analytical tools.

#### 4.8: Normalize Name and Synonym Properties

Align naming conventions across different entity types:

```cypher
-- For physical entities: use commonName as primary name, store alternatives as synonyms
MATCH (n:PhysicalEntity) 
WHERE n.synonyms IS NULL 
SET n.synonyms = n.name, n.name = n.commonName 
REMOVE n.commonName;

-- For events: set first synonym as primary name if not set
MATCH (n:Event) 
WHERE n.synonyms IS NULL AND n.name IS NOT NULL 
SET n.synonyms = n.name, n.name = n.synonyms[0];

-- For reference entities: set first synonym as primary name if not set
MATCH (n:ReferenceEntity) 
WHERE n.synonyms IS NULL AND n.name IS NOT NULL 
SET n.synonyms = n.name, n.name = n.synonyms[0];

-- Use gene name as primary if available
MATCH (n:ReferenceEntity) 
WHERE n.name IS NULL AND n.geneName IS NOT NULL 
SET n.synonyms = n.geneName, n.name = n.geneName[0];

-- Fall back to identifier if no name available
MATCH (n:ReferenceEntity) 
WHERE n.name IS NULL 
SET n.name = n.identifier;

-- For entities with displayName, use as primary if appropriate
MATCH (n:PhysicalEntity) 
WHERE n.name IS NULL AND n.displayName STARTS WITH n.synonyms[0]
SET n.name = n.synonyms[0];
```

---

## Summary of Changes by Changelog

| Version | Purpose |
|---------|---------|
| 0000 | Remove metadata, filter for human data, restructure properties, reverse relationships |
| 0100 | (No changes - checkpoint) |
| 0200 | Add synonym nodes and assign entity type labels |
| 0300 | Standardize naming conventions across entity types |

---

## Notes and Best Practices

- **Testing:** Run these operations on a backup copy first to verify the results
- **Performance:** Use batched transactions (`IN TRANSACTIONS OF x ROWS`) for large datasets to prevent memory issues
- **APOC Requirements:** Some operations require the APOC library to be installed
- **Backup:** Always maintain a backup of the original dump before running cleanup operations
- **Monitoring:** Monitor query execution time and memory usage during cleanup operations

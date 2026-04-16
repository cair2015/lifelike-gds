# Reactome notes for metabolite-based pathway analysis

## Overview

These notes summarize key modeling issues when using **Reactome** for **metabolite-based pathway analysis**, especially when seeding **PhysicalEntity** nodes for **PageRank**, **personalized PageRank (PPR)**, or **random walk with restart (RWR)**.

The main challenge is that Reactome is a rich biological knowledge graph, not a simple metabolite network. As a result, graph-based analysis can be biased by database representation details unless the graph and seed strategy are designed carefully.

---

## 1. Metabolite name mapping and ChEBI

A metabolite name from a lab report or metabolomics list usually does **not** map cleanly to a single Reactome node.

### Why this happens

Reactome stores pathway participants as **PhysicalEntity** objects. The same chemical identity is typically represented through **ReferenceEntity / ChEBI** relationships, and the actual pathway participant may differ from the input metabolite label because of:

- protonation state
- conjugated form
- activated or cofactor-bound form
- compartment-specific instance
- a related small-molecule form used in the reaction context

### Implication

Simple one-name-to-one-node matching is usually incomplete.

For a given metabolite, we may need to gather:

1. a canonical compound name or ChEBI identifier
2. related relevant chemical forms used in Reactome
3. all corresponding **PhysicalEntity** instances

### Recommended mapping strategy

- Start from a canonical metabolite name and/or **ChEBI** identifier.
- Expand to related chemical forms that may appear in Reactome pathway context.
- Collect all matched **PhysicalEntity** nodes as candidate pathway participants.

### Practical takeaway

**Map broadly at the compound level first, then resolve to Reactome PhysicalEntities.**

---

## 2. One chemical can map to many PhysicalEntities, which makes ranking unfair

A single metabolite may correspond to **multiple Reactome PhysicalEntity nodes**, including:

- different compartments
- different pathway contexts
- sometimes multiple entities even within the same compartment

### Problem

If each matched PhysicalEntity is given seed weight = 1, then metabolites with many Reactome representations receive **more total starting mass** than metabolites with fewer representations.

This makes the ranking partly reflect **database representation density**, not biology.

### Example

- Metabolite A maps to 8 PhysicalEntities -> total seed mass = 8
- Metabolite B maps to 1 PhysicalEntity -> total seed mass = 1

If both are equally important abnormal findings, this is unfair.

### Recommended fix

Assign weight at the **metabolite level**, not the PhysicalEntity level.

If metabolite `m` maps to `k` PhysicalEntities, distribute one total unit of mass across those nodes:

```text
weight per matched node = 1 / k
```

This ensures that each metabolite contributes the same total seed mass.

### Better formulation

For multiple metabolites, define a personalization vector so that:

- each metabolite gets equal total mass, or
- each metabolite gets a biologically motivated weight (for example based on z-score, fold change, or confidence)
- that mass is split across all matched PhysicalEntities

### Practical takeaway

**Each metabolite should contribute one normalized total seed weight, regardless of how many Reactome PhysicalEntities it maps to.**

---

## 3. Complex and EntitySet issues

Reactome contains additional abstractions that can distort shortest-path and diffusion-based analyses.

### 3.1 Complex

A **Complex** is a PhysicalEntity that may contain:

- proteins
- chemicals
- other complexes

Complexes can be nested several layers deep.

#### Problem

If shortest path or diffusion analysis traverses component relationships freely, paths can become long because of **representation structure**, not pathway mechanism.

A shortest path may therefore reflect:

- recursive containment
- complex nesting
- bookkeeping structure

rather than meaningful biochemical flow.

### 3.2 EntitySet

An **EntitySet** represents a set of alternative or functionally related entities.

Important point: members of an EntitySet are **not necessarily all participating** in the event at the same time.

EntitySets can also contain other EntitySets.

#### Problem

If graph traversal treats EntitySet membership like an ordinary pathway edge, paths may become formally connected but biologically weak.

A path through EntitySet edges may mean:

- "one of these could fulfill the role"

rather than:

- "this exact molecule actually participated"

### Overall issue

If all Reactome relations are treated equally in shortest path or PageRank, the analysis can be dominated by:

- membership structure
- containment structure
- recursive abstraction

instead of actual biochemical event flow.

### Practical takeaway

**Complex and EntitySet are useful for mapping and interpretation, but they should not usually be treated as ordinary pathway-flow edges.**

---

## 4. Suggested solutions

### 4.1 Separate mapping edges from mechanistic pathway edges

Use two conceptual graph layers.

#### A. Resolution / mapping layer

Use this layer only to find seed nodes and interpret hits.

Include relations such as:

- metabolite name -> ChEBI
- ChEBI / ReferenceEntity -> PhysicalEntity
- EntitySet membership
- Complex components

#### B. Analysis / propagation layer

Use this layer for PageRank, diffusion, or pathway traversal.

Include mainly:

- PhysicalEntity -> Reaction
- Reaction -> PhysicalEntity
- optional catalyst/regulation edges

### Key principle

**Use Complex and EntitySet to resolve and explain nodes. Use reactions to propagate signal.**

---

### 4.2 Normalize seed weights

For each metabolite:

1. collect all matched PhysicalEntities
2. assign one total unit of seed mass to the metabolite
3. split that mass across its matched PhysicalEntities

This prevents over-weighting compounds with many Reactome matches.

---

### 4.3 Prefer personalized PageRank / random walk with restart

Instead of ordinary global PageRank, use a seeded method such as:

- **personalized PageRank (PPR)**
- **random walk with restart (RWR)**

The personalization vector should be based on normalized metabolite-level weights.

### Why this is better

This makes ranking reflect the abnormal metabolite set rather than generic graph centrality.

---

### 4.4 Avoid unrestricted traversal through Complex and EntitySet

For shortest path or graph distance calculations, do not treat all membership/component edges as standard biological edges.

Options:

- exclude them from traversal
- assign them high cost
- use them only in preprocessing and post hoc interpretation

### Example edge-cost idea

- reaction input/output edges = low cost
- catalyst/regulation edges = moderate cost
- complex decomposition edges = high cost
- EntitySet membership edges = very high cost, or mapping-only

This helps shortest paths reflect real biochemical flow rather than ontology structure.

---

### 4.5 Keep complexes as pathway-role nodes during analysis

Instead of recursively breaking every complex into its base components during propagation:

- keep the Complex as a node in the analysis graph
- allow it to connect to reactions in its pathway role
- decompose it later for interpretation if needed

This reduces path inflation and preserves pathway meaning.

---

### 4.6 Use EntitySet conservatively

Good use cases for EntitySet:

- identifying candidate participants during seed mapping
- helping interpret top-ranked nodes afterward

Less reliable use:

- recursive traversal through EntitySet membership as if it were a causal pathway edge

Safer options:

- use EntitySet only for mapping
- collapse the set to a meta-node
- split weight conservatively across members when expansion is unavoidable

---

### 4.7 Consider significance against a null model

Highly connected graph regions can still dominate ranking.

To reduce this bias:

- compare observed scores to randomized seed sets
- preserve seed-set properties during permutation when possible
- report z-scores or empirical p-values in addition to raw ranks

This makes the ranking more interpretable and statistically defensible.

---

## Recommended workflow

A practical workflow for metabolite-based Reactome analysis:

1. normalize metabolite names to canonical compounds / ChEBI
2. gather all relevant Reactome PhysicalEntities for each metabolite
3. split each metabolite's seed weight across its matched entities
4. build a reaction-centered propagation graph
5. exclude or penalize Complex and EntitySet membership edges during propagation
6. run personalized PageRank or random walk with restart
7. interpret top-ranked nodes using Complex / EntitySet decomposition afterward

---

## Main takeaway

The main risk is that Reactome's rich biological representation introduces **structural duplication and abstraction** that can bias graph analysis.

The main fix is:

- **map broadly**
- **seed fairly**
- **propagate through reaction flow, not containment or membership structure**

In short:

> Map broadly at the metabolite / ChEBI level, normalize seeds at the metabolite level, and use reaction-centered propagation while treating Complex and EntitySet mainly as mapping and interpretation constructs.

---

## Optional concise summary

- Metabolite labels do not map one-to-one to Reactome nodes; use **ChEBI-centered mapping** and gather all relevant PhysicalEntities.
- One metabolite can map to many PhysicalEntities; normalize seed mass so each metabolite contributes equally.
- Complex and EntitySet can create long or misleading paths if treated as ordinary graph edges.
- Use **reaction-centered personalized PageRank / RWR** for analysis.
- Use **Complex / EntitySet mainly for seed resolution and result interpretation**, not unrestricted propagation.

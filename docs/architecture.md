# lifelike-gds: Architecture & Usage Guide

## Overview

**lifelike-gds** is a Python library for biological pathway network analysis. It provides tools to query a graph database of biological pathways (currently Reactome), run influence and shortest-path analyses on those networks, and export results for visualization or downstream use.

The primary use case is **metabolite-based pathway analysis**: given a list of metabolites, identify which pathways and biological entities are most influenced by those metabolites using personalized PageRank (radiate analysis) and trace path extraction.

Results can be visualized as Sankey diagrams in the [Lifelike app](https://public.lifelike.bio/).

---

## Architecture

```
lifelike_gds/
├── network/           # Generic graph layer (NetworkX wrappers, I/O, algorithms)
│   ├── graph_utils.py       # DirectedGraph / MultiDirectedGraph classes
│   ├── graph_algorithms.py  # Path-finding and centrality algorithms
│   ├── graph_props.py       # Node/edge property accessors and filters
│   ├── graph_io.py          # Read/write graph files (JSON, GraphML, Excel)
│   ├── trace_utils.py       # Build and manage trace networks
│   ├── trace_export.py      # Export trace results to JSON
│   └── collection_utils.py  # Dictionary and collection utilities
├── <db>_network/      # Database-specific layer (one per graph database backend)
│   ├── database.py          # Database connection and query API
│   ├── reactome.py          # Reactome-specific graph setup and constants
│   ├── trace_graph_nx.py    # TraceGraphNx: main graph wrapper with DB integration
│   ├── trace_graph_utils.py # PageRank, Sankey/Cytoscape export helpers
│   ├── radiate_trace.py     # RadiateTrace: PageRank-based radiate analysis
│   ├── shortest_paths_trace.py  # ShortestPathTrace: shortest path analysis
│   └── inbetweenness_trace.py   # InBetweennessTrace: betweenness centrality
└── utils/             # General utilities (Excel, Pandas, I/O, strings)
```

### Layer responsibilities

| Layer | Responsibility |
|-------|---------------|
| `network/` | Pure graph logic: algorithms, property access, file I/O, trace management. No database dependency. |
| `<db>_network/` | Database connectivity, query execution, and domain-specific graph loading. Currently implemented for one backend; designed to be replaced/extended. |
| `utils/` | Output formatting helpers (Excel, TSV, string normalization). |

### Core classes

```
DatabaseConnection (database.py)
    └── ReactomeDB – queries for ChEBI, stId, gene, and pathway node lookups

TraceGraphNx (trace_graph_nx.py)
    └── DirectedGraph (graph_utils.py, wraps nx.DiGraph)
        └── stores node sets, trace networks, and graph-level metadata

RadiateTrace (radiate_trace.py)  ← extends TraceGraphNx
ShortestPathTrace (shortest_paths_trace.py)  ← extends TraceGraphNx
InBetweennessTrace (inbetweenness_trace.py)  ← extends TraceGraphNx
```

---

## Key concepts

### PhysicalEntity and ChEBI mapping

Reactome represents pathway participants as **PhysicalEntity** nodes. A metabolite name does not map one-to-one to a Reactome node — the same chemical can appear in multiple forms (compartments, conjugation states, complexes). The correct approach is:

1. Identify the canonical **ChEBI** identifier (or Reactome **stId**) for each metabolite.
2. Query the database for all **PhysicalEntity** nodes linked to that ChEBI/stId.
3. Use those PhysicalEntity nodes as source nodes for analysis.

See [`docs/reactome_metabolite_analysis_notes.md`](reactome_metabolite_analysis_notes.md) for detailed guidance on seed normalization and Complex/EntitySet handling.

### Radiate analysis

Radiate analysis runs **personalized PageRank** (forward and reverse) from a set of source nodes. The result is a ranked list of nodes by how strongly they are influenced by (or influence) the source nodes. This identifies the most relevant pathways, reactions, and genes connected to the input metabolites.

- **Forward PageRank**: signal flows outward from sources — finds downstream targets.
- **Reverse PageRank**: runs on the reversed graph — finds upstream regulators/inputs.

### Trace networks

A **trace network** connects each source node to a selected target node via one or more paths. Traces are computed after radiate analysis: you select high-ranking nodes from the PageRank output, then trace the paths back to the sources.

Trace networks are stored in `graph["trace_networks"]` and can be exported to JSON for visualization.

### Node sets

Named groups of nodes stored in `graph["node_sets"]`. Used to label sources, targets, and analysis subgroups. Each node set carries metadata (display name, description, color).

---

## Workflow: Metabolite Radiate Analysis

The full workflow has four stages. Example notebooks are in [`notebooks/reactome/`](../notebooks/reactome/).

### Stage 1 — Map metabolites to PhysicalEntity source nodes

**Input**: CSV file with ChEBI IDs or Reactome stIds.

```python
from lifelike_gds.<db>_network.database import ReactomeDB

db = ReactomeDB(dbname="reactome", uri="localhost", username="root", password="")

# Option A: map via ChEBI
chebi_ids = ["38290", "15422"]  # numeric part only
ref_nodes = db.get_reference_nodes_by_chebi_ids(chebi_ids)
source_nodes = db.get_entity_nodes_by_chebi_ids(chebi_ids)

# Option B: map via Reactome stId
st_ids = ["R-HSA-29358", "R-HSA-15422"]
source_nodes = db.get_nodes_by_attr(attr_values=st_ids, attr_name="stId")
```

Export matches for review:

```python
from lifelike_gds.utils.excel_utils import write as write_excel
import pandas as pd

df = pd.DataFrame(source_nodes)
write_excel(df, "output/matched_physical_entities.xlsx")
```

### Stage 2 — Run radiate analysis

```python
from lifelike_gds.<db>_network.reactome import Reactome
from lifelike_gds.<db>_network.radiate_trace import RadiateTrace

# Load the Reactome pathway graph (excludes common currency metabolites)
reactome = Reactome(db)
trace_graph = RadiateTrace(graphsource=reactome)
trace_graph.init_default_graph(exclude_currency=True)

# Register source nodes as a named node set
trace_graph.set_node_set_from_arango_nodes(
    source_nodes,
    name="Input metabolites",
    key="sources"
)

# Run forward and reverse personalized PageRank
trace_graph.set_pagerank_and_numreach(source_set="sources", pagerank_prop="pagerank")

# Export top-ranked nodes to Excel (forward + reverse sheets)
trace_graph.export_pagerank_data(
    "output/radiate_analysis.xlsx",
    pagerank_prop="pagerank",
    num_nodes=4000
)
```

The output Excel file has two sheets:
- **pagerank** — nodes ranked by forward PageRank (downstream of sources)
- **rev-pagerank** — nodes ranked by reverse PageRank (upstream of sources)

### Stage 3 — Select nodes and run traces

Open the Excel file and identify high-ranking nodes of interest (e.g., pathways, reactions, proteins). Note their database IDs.

**Forward trace** (from sources to selected nodes from the `pagerank` sheet):

```python
selected_node_ids = ["R-HSA-5663213", "R-HSA-1430728"]  # from pagerank sheet

trace_graph.add_traces_from_sources_to_each_selected_nodes(
    sources_key="sources",
    selected_node_ids=selected_node_ids
)

# Export trace graph to .graph JSON file
from lifelike_gds.network.graph_io import write_json
from lifelike_gds.<db>_network.trace_graph_utils import write_sankey_file

write_sankey_file(trace_graph.graph, "output/metabolites_traces.graph")
```

**Reverse trace** (from selected nodes back to sources, for nodes from `rev-pagerank` sheet):

```python
trace_graph.add_selected_nodes_trace_networks(
    sources_key="sources",
    selected_node_ids=selected_node_ids,
    reverse=True
)
write_sankey_file(trace_graph.graph, "output/metabolites_rev_traces.graph")
```

### Stage 4 — Visualize in Lifelike

Upload the `.graph` JSON file to [https://public.lifelike.bio/](https://public.lifelike.bio/) and open it as a **Sankey diagram**. The diagram shows the flow of influence from source metabolites through intermediate nodes to the selected targets.

---

## Environment configuration

Create a `.env` file in the project root (or notebook working directory):

```bash
ARANGO_URI=localhost
ARANGO_USER=root
ARANGO_PASSWORD=your_password
ARANGO_DATABASE=reactome
```

The database classes load these automatically via `python-dotenv`.

---

## Installation

```bash
# Install in editable mode with dev extras
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"
```

**Key dependencies**:

| Package | Purpose |
|---------|---------|
| `networkx < 3.0` | Graph data structure and algorithms |
| `pandas >= 2.0` | Data manipulation and Excel output |
| `numpy >= 1.25` | Numerical operations |
| `scipy >= 1.9` | Sparse matrix support for PageRank |
| `openpyxl`, `xlsxwriter` | Excel read/write |
| `python-dotenv` | `.env` configuration loading |
| `neo4j >= 5.28.3` | Neo4j driver (for upcoming backend) |

---

## Graph I/O reference

```python
from lifelike_gds.network.graph_io import (
    read_json,          # load .graph or other JSON graph file
    read_apoc_json,     # load APOC-format Neo4j export
    write_json,         # write JSON (handles numpy types)
    nodes2excel,        # export node properties to Excel
    write_graphml,      # export graph to GraphML
)
```

### Reading an existing `.graph` file

```python
G = read_json("output/metabolites_traces.graph")
```

### Exporting node properties to Excel

```python
nodes2excel(trace_graph.graph, "output/nodes.xlsx")
```

---

## Trace export reference

`trace_export.py` provides an LLM-friendly JSON export format with explicit path steps.

```python
from lifelike_gds.network.trace_export import export_trace_centered_json, TraceExportConfig

config = TraceExportConfig(
    mode="normal",           # "normal", "reverse", or "mixed"
    ranking_method="pagerank"
)

result = export_trace_centered_json(
    G=trace_graph.graph,
    source_node_ids=source_node_ids,
    selected_node_ids=selected_node_ids,
    config=config,
    output_file="output/traces.json"
)
```

The output structure:

```json
{
  "analysis_context": { "mode": "...", "ranking_method": "...", "..." },
  "node_dictionary": { "<node_id>": { "label": "...", "type": "...", "pagerank": 0.001 } },
  "selected_nodes": [
    {
      "selected_node_id": "...",
      "trace_bundle": [
        {
          "trace_id": "...",
          "start_node_id": "...",
          "direction": "start_to_selected",
          "trace_score": 0.87,
          "path_length": 3,
          "steps": [
            { "step_index": 1, "from_id": "...", "from_label": "...", "relation": "input", "to_id": "...", "to_label": "..." }
          ]
        }
      ]
    }
  ]
}
```

---

## DirectedGraph API

`DirectedGraph` extends `nx.DiGraph` with convenience methods for node/edge property access, node sets, and trace metadata.

```python
from lifelike_gds.network.graph_utils import DirectedGraph

G = DirectedGraph()

# Node access with property filter
nodes = G.get(prop_filter={"type": "Pathway"})          # list of node IDs
nodes = G.getd(prop_filter={"type": "Reaction"})        # list of dicts

# Node sets
G.set_node_set(key="sources", nodes=["n1", "n2"], name="Input metabolites")
source_nodes = G.node_set("sources")

# Edge access
edges = G.gete(prop_filter={"relation": "input"})

# Successors / predecessors
downstream = G.get_successors({"n1", "n2"})
upstream = G.get_predecessors({"n1", "n2"})

# Trim leaf/root nodes
G_trimmed = trim_leaves(G)
```

---

## Graph algorithms reference

```python
from lifelike_gds.network.graph_algorithms import (
    shortest_paths,               # one shortest path per source-target pair
    all_shortest_paths,           # all shortest paths between sets
    all_simple_paths,             # all simple paths up to cutoff length
    eigenvector_influence,        # eigenvector centrality from source nodes
    katz_influence,               # Katz centrality variant
)
```

---

## Notebooks

| Notebook | Description |
|----------|-------------|
| [`Metabolites_Radiate_Analysis_with_chebi.ipynb`](../notebooks/reactome/Metabolites_Radiate_Analysis_with_chebi.ipynb) | Full workflow using ChEBI IDs as input |
| [`Metabolites_Radiate_Analysis_with_stIds.ipynb`](../notebooks/reactome/Metabolites_Radiate_Analysis_with_stIds.ipynb) | Full workflow using Reactome stIds as input |
| [`metabolites_radiate_traces.ipynb`](../notebooks/reactome/metabolites_radiate_traces.ipynb) | Trace path extraction from radiate analysis output |
| [`Reactome_shortest_paths_example.ipynb`](../notebooks/reactome/Reactome_shortest_paths_example.ipynb) | Shortest path analysis between two node sets |

---

## Reactome graph structure notes

The Reactome graph loaded by `Reactome.initiate_trace_graph()` uses the following edge types for propagation:

| Relation | Meaning |
|----------|---------|
| `input` | Metabolite/entity is input to a reaction |
| `output` | Reaction produces this entity |
| `catalyzes` | Catalyst activates a reaction |
| `regulates` | Regulator controls a reaction |
| `activeUnitOf` | Active unit of a complex |

**Currency metabolites** (ATP, NADH, H₂O, etc.) are excluded by default to prevent spurious high-connectivity shortcuts. See `reactome.SECONDARY_CHEMS` for the full list.

Complex and EntitySet membership edges are included in node lookup but should be used carefully in propagation — see [`reactome_metabolite_analysis_notes.md`](reactome_metabolite_analysis_notes.md) for details.

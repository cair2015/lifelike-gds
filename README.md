# GDS Public

Knowledge mining project for Lifelike. "Forked" from SBRG/GDS including only the NW-arangodb branch. This project provides graph database analysis tools for network analysis, including support for Neo4j, ArangoDB, and various bioinformatics datasets.

## Project Overview

**GDS Public** is designed for:
- Knowledge mining and graph database management
- Network analysis and shortest path algorithms
- Radiate analysis for exploring network connections
- Integration with Neo4j and ArangoDB databases

## Requirements

- Python ≥ 3.11
- `uv` package manager (lightweight, fast replacement for pip/pipenv)

## Quick Start

### 1. Install `uv` (if not already installed)

On macOS/Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows:
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Or install via Homebrew (macOS):
```bash
brew install uv
```

### 2. Set Up the Development Environment

From the root directory of the project:

```bash
just setup
```

This runs `uv sync` to create a Python virtual environment and install all dependencies.

### 3. Verify Installation

```bash
just lint
```

## Using `just` Commands

This project uses a [justfile](justfile) for common tasks. View all available commands:

```bash
just --list
```

Common commands:
- `just setup` - Create and sync the Python environment
- `just add <package>` - Add a runtime dependency
- `just add-dev <package>` - Add a development dependency
- `just lint` - Run code linting checks
- `just format` - Format code
- `just fix` - Auto-fix linting and formatting issues
- `just typecheck` - Run type checking
- `just test` - Run tests
- `just sync` - Update the lockfile and environment
- `just lock` - Update the lockfile

## Working with Jupyter Notebooks

Notebooks are located in the [notebooks/](notebooks/) directory. To run a notebook:

1. Launch Jupyter:
   ```bash
   uv run jupyter notebook
   ```

2. Navigate to the desired notebook in the Jupyter interface

3. The notebooks demonstrate various analyses:
   - **Radiate Analysis**: Explore network graphs radiating from nodes
   - **Shortest Paths**: Find optimal paths between nodes
   - **Intersection Analysis**: Identify common pathways
   - **Network Traces**: Track connections through networks

## Project Structure

```
.
├── src/
│   └── lifelike_gds/          # Main package
│       ├── arango_network/    # ArangoDB integration
│       ├── graph/             # Graph analysis algorithms
│       ├── network/           # Network utilities
│       └── utils/             # Utility functions
├── notebooks/                 # Jupyter notebooks and examples
│   ├── CfB_Workshop/          # CfB training materials
│   ├── UCSD_Workshop/         # UCSD training materials
│   ├── generic/               # Generic analysis examples
│   ├── neo4j_general/         # Neo4j examples
│   └── reactome/              # Reactome database examples
├── data/                      # Input data for analyses
│   ├── endo/                  # Endocytosis pathway data
│   ├── eot/                   # End-of-trail data
│   └── metal_biomass/         # Metal/biomass data
├── arangodb/                  # ArangoDB configuration and setup
├── neo4j-db/                  # Neo4j database notes
├── docs/                      # Documentation files
├── pyproject.toml             # Project configuration
├── justfile                   # Task automation
└── README.md                  # This file
```

## Editor Configuration

### VS Code

VS Code will automatically detect the `uv` environment. To ensure proper Python environment detection:

1. Open the Command Palette (`Cmd+Shift+P` on macOS, `Ctrl+Shift+P` on Windows/Linux)
2. Search for and select "Python: Select Interpreter"
3. Choose the interpreter from the `uv` environment (usually shown with the project name)

To enable auto-formatting with Ruff:

1. Install the Ruff extension: `charliermarsh.ruff`
2. Add to your `.vscode/settings.json`:
   ```json
   {
       "[python]": {
           "editor.formatOnSave": true,
           "editor.defaultFormatter": "charliermarsh.ruff"
       }
   }
   ```

### PyCharm

1. Go to **PyCharm → Preferences** (macOS) or **File → Settings** (Linux/Windows)
2. Navigate to **Project → Python Interpreter**
3. Click the gear icon and select **Add**
4. Choose **Existing Environment** and locate the Python executable in the `uv` environment
5. To find the environment path, run: `uv venv --no-activation-script --python /path/to/python`

## Development Workflow

### Code Quality

This project enforces code quality standards using [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.

**Before committing:**
```bash
just fix      # Auto-fixes linting and formatting issues
just typecheck # Run type checking
```

### Adding Dependencies

To add a new runtime dependency:
```bash
just add requests
```

To add a development dependency:
```bash
just add-dev pytest
```

## Running Tests

```bash
just test
```

## Contributing

1. Create a new branch for your feature or fix
2. Make your changes and ensure code quality:
   ```bash
   just fix
   just typecheck
   ```
3. Run tests to ensure everything works:
   ```bash
   just test
   ```
4. Commit and push your changes

## License

See [LICENSE](LICENSE) for license information.

## References

- **Original Project**: [SBRG/GDS](https://github.com/SBRG/GDS)
- **Lifelike Homepage**: https://lifelike.bio/
- **Neo4j Documentation**: https://neo4j.com/docs/
- **uv Documentation**: https://docs.astral.sh/uv/


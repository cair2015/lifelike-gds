import os
from pathlib import Path

import pytest

from pathway_graphx.utils import config_utils


def reset_env_loader():
    config_utils._env_loaded = False


def test_read_config_reads_explicit_environment_values(monkeypatch):
    reset_env_loader()
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "demo")
    monkeypatch.setenv("NEO4J_ENCRYPTED", "yes")

    config = config_utils.read_config("neo4j")

    assert config == {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": "secret",
        "database": "demo",
        "encrypted": True,
    }


def test_read_config_uses_default_neo4j_database_and_validates_required_keys(monkeypatch, tmp_path):
    reset_env_loader()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)
    monkeypatch.delenv("NEO4J_ENCRYPTED", raising=False)

    config = config_utils.read_config("neo4j")
    assert config["database"] == "neo4j"
    assert config["encrypted"] is False

    reset_env_loader()
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    with pytest.raises(KeyError, match="NEO4J_PASSWORD"):
        config_utils.read_config("neo4j")


def test_read_config_loads_values_from_nearby_dotenv(monkeypatch, tmp_path):
    reset_env_loader()
    project = tmp_path / "project"
    nested = project / "nested" / "child"
    nested.mkdir(parents=True)
    env_file = project / ".env"
    env_file.write_text(
        "NEO4J_URI=bolt://example:7687\n"
        "NEO4J_USER=alice\n"
        "NEO4J_PASSWORD=fromfile\n"
        "NEO4J_ENCRYPTED=1\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(nested)
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)
    monkeypatch.delenv("NEO4J_ENCRYPTED", raising=False)

    config = config_utils.read_config("neo4j")

    assert config["uri"] == "bolt://example:7687"
    assert config["user"] == "alice"
    assert config["password"] == "fromfile"
    assert config["database"] == "neo4j"
    assert config["encrypted"] is True


def test_candidate_env_paths_walk_up_from_cwd(monkeypatch, tmp_path):
    reset_env_loader()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    paths = config_utils._candidate_env_paths()

    assert paths[0] == nested / ".env"
    assert paths[1] == nested.parent / ".env"
    assert all(isinstance(path, Path) for path in paths)

"""
Configuration utilities for environment-driven database connections.

Provides functions for loading configuration from environment variables (.env file).
Uses python-dotenv for environment variable management.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file from project root or current directory
_env_loaded = False


def _load_env_file():
    """Load .env file if not already loaded."""
    global _env_loaded
    
    if _env_loaded:
        return
    
    # Try to find .env file in common locations
    env_paths = [
        Path(".env"),  # Current directory
        Path.cwd() / ".env",  # Current working directory
        Path(__file__).parent / ".env",  # module directory
        Path(__file__).parent.parent.parent / ".env",  # Project root (src/lifelike_gds/..)
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded .env file from {env_path}")
            _env_loaded = True
            return
    
    # Load from system environment even if no .env file exists
    _env_loaded = True
    logger.debug("No .env file found, using system environment variables")



def read_config(db_name: str = "neo4j") -> Dict[str, Any]:
    """
    Read database configuration from environment variables.
    
    Environment variables expected:
        {DB}_URI: Connection URI (e.g., bolt://localhost:7687)
        {DB}_USER: Database username
        {DB}_PASSWORD: Database password
        {DB}_DATABASE: Database name (default: neo4j for Neo4j)
        {DB}_ENCRYPTED: Optional flag for encrypted connections

    Args:
        db_name: Configuration prefix used for environment variables.
            For Neo4j use "neo4j". For ArangoDB use "arango".

    Returns:
        Configuration dictionary with uri, user, password, database, encrypted

    Raises:
        KeyError: If required environment variables are missing
    """
    _load_env_file()
    
    # Get required configuration from environment
    db = db_name.upper()
    uri = os.getenv(f"{db}_URI")
    user = os.getenv(f"{db}_USER")
    password = os.getenv(f"{db}_PASSWORD")
    
    if not uri or not user or not password:
        missing = [
            var for var, val in [
                (f"{db}_URI", uri),
                (f"{db}_USER", user),
                (f"{db}_PASSWORD", password),
            ] if not val
        ]
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise KeyError(error_msg)
    
    # Get optional configuration
    default_database = "neo4j" if db == "NEO4J" else None
    database = os.getenv(f"{db}_DATABASE", default_database)
    encrypted_str = os.getenv(f"{db}_ENCRYPTED", "false").lower()
    encrypted = encrypted_str in ("true", "1", "yes", "on")

    config = {
        "uri": uri,
        "user": user,
        "password": password,
        "database": database,
        "encrypted": encrypted,
    }

    logger.debug(f"Loaded configuration for {db_name} from environment variables")
    return config

def get_neo4j_config() -> Dict[str, Any]:
    """
    Get Neo4j configuration dictionary.
    
    Convenience wrapper around read_config() that reads Neo4j-specific environment variables.
    
    Returns:
        Dictionary with keys: uri, user, password, database, encrypted
    """
    return read_config("neo4j")


def get_arango_config() -> Dict[str, Any]:
    """
    Get ArangoDB configuration dictionary.

    Convenience wrapper around read_config() that reads ArangoDB-specific environment variables.

    Returns:
        Dictionary with keys: uri, user, password, database, encrypted
    """
    return read_config("arango")


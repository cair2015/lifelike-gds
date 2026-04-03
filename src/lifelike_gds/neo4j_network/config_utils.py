"""
Configuration utilities for Neo4j connections.

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
        Path(__file__).parent / ".env",  # neo4j_network directory
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


def read_config() -> Dict[str, Any]:
    """
    Read Neo4j configuration from environment variables.
    
    Environment variables expected:
        NEO4J_URI: Neo4j connection URI (e.g., bolt://localhost:7687)
        NEO4J_USER: Database username
        NEO4J_PASSWORD: Database password
        NEO4J_DATABASE: Database name (default: neo4j)
        NEO4J_ENCRYPTED: Whether to use encryption (true/false)
    
    Returns:
        Configuration dictionary with neo4j settings
        
    Raises:
        KeyError: If required environment variables are missing
    """
    _load_env_file()
    
    # Get required configuration from environment
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    
    if not uri or not user or not password:
        missing = [
            var for var, val in [
                ("NEO4J_URI", uri),
                ("NEO4J_USER", user),
                ("NEO4J_PASSWORD", password),
            ] if not val
        ]
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise KeyError(error_msg)
    
    # Get optional configuration
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    encrypted_str = os.getenv("NEO4J_ENCRYPTED", "false").lower()
    encrypted = encrypted_str in ("true", "1", "yes", "on")
    
    config = {
        "neo4j": {
            "uri": uri,
            "user": user,
            "password": password,
            "database": database,
            "encrypted": encrypted,
        }
    }
    
    logger.debug("Successfully loaded Neo4j configuration from environment variables")
    return config


def get_neo4j_config() -> Dict[str, Any]:
    """
    Get Neo4j configuration dictionary.
    
    Convenience wrapper around read_config() that returns just the neo4j section.
    
    Returns:
        Dictionary with keys: uri, user, password, database, encrypted
    """
    config = read_config()
    return config.get("neo4j", {})


def get_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a specific Neo4j configuration value by environment variable name.
    
    Args:
        key: Environment variable name (without NEO4J_ prefix)
        default: Default value if not found
        
    Returns:
        Configuration value or default
        
    Example:
        uri = get_config_value("URI")  # Gets NEO4J_URI
        user = get_config_value("USER", default="neo4j")  # Gets NEO4J_USER
    """
    _load_env_file()
    env_var = f"NEO4J_{key.upper()}"
    return os.getenv(env_var, default)

"""Configuration utilities for environment-driven Neo4j connections."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_env_loaded = False


def _load_env_file() -> None:
    """Load a nearby ``.env`` file once before reading environment variables."""
    global _env_loaded

    if _env_loaded:
        return

    env_paths = [
        Path('.env'),
        Path.cwd() / '.env',
        Path(__file__).parent / '.env',
        Path(__file__).parent.parent.parent / '.env',
    ]

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug('Loaded .env file from %s', env_path)
            _env_loaded = True
            return

    _env_loaded = True
    logger.debug('No .env file found, using system environment variables')


def read_config(db_name: str = 'neo4j') -> dict[str, Any]:
    """Read environment-driven database configuration.

    Expected environment variables:
        {DB}_URI
        {DB}_USER
        {DB}_PASSWORD
        {DB}_DATABASE
        {DB}_ENCRYPTED
    """
    _load_env_file()

    db = db_name.upper()
    uri = os.getenv(f'{db}_URI')
    user = os.getenv(f'{db}_USER')
    password = os.getenv(f'{db}_PASSWORD')

    if not uri or not user or not password:
        missing = [
            var
            for var, val in [
                (f'{db}_URI', uri),
                (f'{db}_USER', user),
                (f'{db}_PASSWORD', password),
            ]
            if not val
        ]
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise KeyError(error_msg)

    database = os.getenv(f'{db}_DATABASE', 'neo4j' if db == 'NEO4J' else None)
    encrypted = os.getenv(f'{db}_ENCRYPTED', 'false').lower() in {'true', '1', 'yes', 'on'}

    config = {
        'uri': uri,
        'user': user,
        'password': password,
        'database': database,
        'encrypted': encrypted,
    }
    logger.debug('Loaded configuration for %s from environment variables', db_name)
    return config


def get_neo4j_config() -> dict[str, Any]:
    """Return the Neo4j configuration dictionary."""
    return read_config('neo4j')

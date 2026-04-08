"""
Path utilities for finding project directories and resources.
"""

from pathlib import Path


def get_project_root(marker_file: str = 'pyproject.toml') -> Path:
    """
    Find the project root directory by looking for a marker file.
    
    Searches up from the current file location until it finds the marker file
    (typically pyproject.toml, setup.py, etc.).
    
    Args:
        marker_file: Filename to use as project root marker (default: 'pyproject.toml')
        
    Returns:
        Path to project root directory
        
    Example:
        >>> project_root = get_project_root()
        >>> data_dir = project_root / 'data'
    """
    for parent in Path(__file__).parents:
        if (parent / marker_file).exists():
            return parent
    # Fallback to workspace root if marker not found
    return Path(__file__).parents[-1]

#!/usr/bin/env python3
from pathway_graphx.utils.shell_utils import get_command_output


def commit_hash():
    """
    Get current commit hash.
    :return: string SHA1 hash.
    """
    return get_command_output("git rev-parse HEAD")

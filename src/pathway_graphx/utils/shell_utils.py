#!/usr/bin/env python3
import subprocess


def get_command_output(command):
    """
    Get output of shell command as string.
    :param command: string command.
    :return:
    """
    return subprocess.check_output(command.split()).strip().decode()

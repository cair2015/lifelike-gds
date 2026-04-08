#!/usr/bin/env python3
import gzip
import sys


def gzip_stdout(string):
    """
    Write string to stdout gzipped.
    :param string: str
    :return:
    """
    with sys.stdout.buffer as fp:
        fp.write(gzip.compress(string.encode("utf-8")))

#!/usr/bin/env python3
import re


def join(j, values):
    return j.join(map(str, values))


def uncapitalize(string):
    """
    Try to make the first letter of a string lower case if it is not a part of an Acronym etc.
    :param string: str
    :return: str
    """
    try:
        word = string.split()[0]
    except IndexError:
        return string  # empty string
    # has to look like a word capitalization-wise and contain min. 1 vowel
    vowels = set("AEIOUY")
    if re.fullmatch("[A-Z][a-z]*", word) and not vowels.isdisjoint(word.upper()):
        return string[0].lower() + string[1:]
    return string


def ellipses(s, trunc="...", limit=30):
    if len(s) < limit:
        return s
    return s[:limit] + trunc


def name2key(s):
    """
    Make a key from a string name, e.g.
    "glycans + genes" -> "glycansGenes"
    :param s: str name
    :return: str key
    """
    words = [w for w in re.split("[ +/{}\[\]]", s) if w]
    return words[0] + "".join(w.capitalize() for w in words[1:])

#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


"""Autocompletion providers for the advanced editor.

Thanks a lot to https://github.com/wolfthefallen/py-GtkSourceCompletion-example for
useful GtkSource examples
"""


import re

from inputremapper.system_mapping import system_mapping
from inputremapper.injection.macros.parse import FUNCTIONS

# no shorthand names
FUNCTION_NAMES = [name for name in FUNCTIONS.keys() if len(name) > 1]
# no deprecated functions
FUNCTION_NAMES.remove("ifeq")


def _get_left_text(iter):
    buffer = iter.get_buffer()
    result = buffer.get_text(buffer.get_start_iter(), iter, True)
    result = re.sub(r"\s", "", result)
    return result.lower()


# regex to search for the beginning of a...
PARAMETER = r".*?[(,=]\s*"
FUNCTION_CHAIN = r".*?\)\s*\.\s*"


def get_incomplete_function_name(iter):
    """Get the word that is written left to the TextIter."""
    left_text = _get_left_text(iter)

    # match foo in:
    #  bar().foo
    #  bar()\n.foo
    #  bar().\nfoo
    #  bar(\nfoo
    #  bar(KEY_A,\nfoo
    #  foo
    match = re.match(rf"(?:{FUNCTION_CHAIN}|{PARAMETER}|^)(\w+)$", left_text)

    if match is None:
        return None

    return match[1]


def get_incomplete_parameter(iter):
    """Get the parameter that is written left to the TextIter."""
    left_text = _get_left_text(iter)

    # match foo in:
    #  bar(foo
    #  bar(a=foo
    #  bar(qux, foo
    #  foo
    match = re.match(rf"(?:{PARAMETER}|^)(\w+)$", left_text)

    if match is None:
        return None

    return match[1]


def propose_symbols(incomplete_name):
    """Find key names that match the input at the cursor."""
    if incomplete_name is None or len(incomplete_name) <= 2:
        return []

    incomplete_name = incomplete_name.lower()

    return [
        name  # GtkSource.CompletionItem(label=name, text=name)
        for name in list(system_mapping.list_names())
        if incomplete_name in name.lower() and incomplete_name != name.lower()
    ]


def propose_function_names(incomplete_name):
    """Find function names that match the input at the cursor."""
    if incomplete_name is None or len(incomplete_name) <= 1:
        return []

    incomplete_name = incomplete_name.lower()

    return [
        name
        for name in FUNCTION_NAMES
        if incomplete_name in name.lower() and incomplete_name != name.lower()
    ]

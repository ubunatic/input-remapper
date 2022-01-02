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

from gi.repository import GtkSource, GObject
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


def _propose_symbols(iter):
    """Find key names that match the input at the cursor."""
    left_text = _get_left_text(iter)

    # match foo in:
    #  bar(foo
    #  bar(a=foo
    #  bar(qux, foo
    #  foo
    match = re.match(rf"(?:{PARAMETER}|^)(\w+)$", left_text)

    if match is None:
        return

    match = match[1]

    return [
        GtkSource.CompletionItem(label=name, text=name)
        for name in list(system_mapping.list_names())
        if match in name.lower() and match != name.lower()
    ]


def _propose_function_names(iter):
    """Find function names that match the input at the cursor."""
    left_text = _get_left_text(iter)

    # match foo in:
    #  bar().foo
    #  bar()\n.foo
    #  bar().\nfoo
    #  bar(\nfoo
    #  foo
    match = re.match(rf"(?:{FUNCTION_CHAIN}|{PARAMETER}|^)(\w+)$", left_text)

    if match is None:
        return

    match = match[1]

    return [
        GtkSource.CompletionItem(label=name, text=name)
        for name in FUNCTION_NAMES
        if match in name.lower() and match != name.lower()
    ]


class FunctionCompletionProvider(GObject.GObject, GtkSource.CompletionProvider):
    """Autocomplete function names"""

    def do_get_name(self):
        return "Functions"

    def do_populate(self, context):
        _, iter = context.get_iter()
        context.add_proposals(self, _propose_function_names(iter), True)


class KeyCompletionProvider(GObject.GObject, GtkSource.CompletionProvider):
    """Autocomplete key names"""

    def do_get_name(self):
        return "Keys"

    def do_populate(self, context):
        _, iter = context.get_iter()
        context.add_proposals(self, _propose_symbols(iter), True)

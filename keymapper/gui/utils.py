#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


class HandlerDisabled:
    """Safely modify a widget without causing handlers to be called.

    Use in a with statement.
    """

    def __init__(self, widget, handler):
        self.widget = widget
        self.handler = handler

    def __enter__(self):
        self.widget.handler_block_by_func(self.handler)

    def __exit__(self, *_):
        self.widget.handler_unblock_by_func(self.handler)

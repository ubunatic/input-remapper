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


"""The advanced editor with a larger code editor."""


from gi.repository import Gtk, GLib, Gdk

from keymapper.gui.basic_editor import SingleEditableMapping


# TODO I need a fucking base class. Avoiding calls and shit from Row.py is a nightmare
#   because its widgets are quite different. Or maybe I need to add more small functions
#   that can be overwritten by the advancedEditor to avoid wrong access to the widgets
class AdvancedEditor(SingleEditableMapping):
    """Maintains the widgets of the advanced editor."""

    def __init__(self, user_interface):
        """TODO"""
        super().__init__(
            delete_callback=self.on_row_removed,
            user_interface=user_interface,
        )

        self.symbol_input = self.get("code_editor")
        self.symbol_input.connect("focus-out-event", self.on_symbol_input_unfocus)
        self.symbol_input.connect("event", self.on_symbol_input_change)

        self.window = self.get("window")
        self.advanced_editor = self.get("advanced_editor")
        self.timeout = GLib.timeout_add(100, self.check_add_new_key)
        self.active_key_button = None

        self.key = None

        self.get("advanced_change_key_button").connect(
            "focus-out-event", self.on_key_button_unfocus
        )

        mapping_list = self.get("mapping_list_advanced")

        if len(mapping_list.get_children()) == 0:
            self.add_empty()

        # select the first entry
        rows = mapping_list.get_children()
        first_row = rows[0]
        self.on_key_button_clicked(first_row.get_children()[0])

    """SingleEditableMapping"""

    def on_symbol_input_change(self, _, event):
        if not event.type in [Gdk.EventType.KEY_PRESS, Gdk.EventType.KEY_RELEASE]:
            # there is no "changed" event for the GtkSourceView editor
            return

        super().on_symbol_input_change()

    def is_waiting_for_input(self):
        return self.get("advanced_change_key_button").get_active()

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        return self.key

    def get_symbol(self):
        """Get the assigned symbol from the middle column."""
        buffer = self.symbol_input.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def display_key(self, key):
        """TODO"""
        self.key = key
        self.active_key_button.set_label(key.beautify())

    def put_together(self, key, symbol):
        pass

    """Editor"""

    def on_row_removed(self):
        # TODO
        pass

    def get(self, name):
        """Get a widget from the window"""
        return self.user_interface.builder.get_object(name)

    def consume_newest_keycode(self, key):
        """TODO"""
        self.refresh_state()

        if key is None:
            return True

        if not self.is_waiting_for_input():
            return True

        self.set_key(key)

        return True

    def check_add_new_key(self):
        """TODO"""
        # TODO
        pass

    def on_key_button_unfocus(self, button, _):
        """When the focus switches to the symbol_input, disable the button."""
        button.set_active(False)

    def on_key_button_clicked(self, button):
        """One of the mapping keys was clicked.

        Load a different mapping into the editor.
        """
        self.active_key_button = button
        # TODO update advanced editor widgets
        # TODO save?

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        mapping_list_advanced = self.get("mapping_list_advanced")
        key_button = Gtk.Button()
        key_button.set_label("new entry")
        key_button.show_all()
        mapping_list_advanced.insert(key_button, -1)

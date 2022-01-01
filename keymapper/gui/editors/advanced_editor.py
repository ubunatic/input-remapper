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


"""The advanced editor with a multiline code editor."""


from gi.repository import Gtk, GLib, Gdk

from keymapper.gui.editors.base import Editor, EditableMapping
from keymapper.gui.custom_mapping import custom_mapping


# TODO test


class SelectionLabel(Gtk.Label):
    """One label per mapping in the preset.

    This wrapper serves as a storage for the information the inherited label represents.
    """

    __gtype_name__ = "Label"

    def __init__(self):
        super().__init__()
        self.key = None
        self.output = None

    def set_key(self, key):
        """Set the key this button represents

        Parameters
        ----------
        key : Key
        """
        self.key = key

    def set_output(self, output):
        """Set the output/symbol this mapping will attempt to write."""
        self.output = output


# TODO changing keys adds duplicate mappings
# TODO I get tons of duplicate
#  DEBUG mapping.py:108: Key((1, 272, 1), (1, 273, 1)) maps to "abcd"
#  EBUG mapping.py:132: Key((1, 272, 1), (1, 273, 1)) cleared
#  logs
class AdvancedEditor(EditableMapping, Editor):
    """Maintains the widgets of the advanced editor."""

    def __init__(self, user_interface):
        self.user_interface = user_interface

        text_input = self.get("code_editor")
        text_input.connect("event", self.on_text_input_change)

        self.window = self.get("window")
        self.timeout = GLib.timeout_add(100, self.check_add_new_key)
        self.active_selection_label = None

        self.get("advanced_key_recording_toggle").connect(
            "focus-out-event", self.on_key_recording_button_unfocus
        )
        self.get("advanced_key_recording_toggle").connect(
            "focus-in-event",
            self.on_key_recording_button_focus,
        )

        mapping_list = self.get("mapping_list_advanced")
        mapping_list.connect("row-activated", self.on_mapping_selected)

        if len(mapping_list.get_children()) == 0:
            self.add_empty()

        super().__init__(user_interface=user_interface)

    def __del__(self, *_):
        """Clear up all timeouts and resources.

        This is especially important for tests.
        """
        if self.timeout:
            GLib.source_remove(self.timeout)
            self.timeout = None

        # TODO disconnect handlers, since those widgets arent deleted and created from
        #  scratch and duplicate constructor calls would cause problems

    def _on_delete_button_clicked(self, *_):
        """The delete button on a single mapped key was clicked."""
        super()._on_delete_button_clicked()
        self.load_custom_mapping()

    def get_delete_button(self):
        return self.get("advanced-delete-mapping")

    def get(self, name):
        """Get a widget from the window"""
        return self.user_interface.builder.get_object(name)

    def check_add_new_key(self):
        """If needed, add a new empty mapping to the list for the user to configure."""
        # TODO. Or a + icon to add a new one?
        return True

    def on_key_recording_button_focus(self, *_):
        """Show user friendly instructions."""
        self.get("advanced_key_recording_toggle").set_label("Press key")

    def on_key_recording_button_unfocus(self, *_):
        """Show user friendly instructions."""
        self.get("advanced_key_recording_toggle").set_label("Change key")

    def on_mapping_selected(self, _=None, list_box_row=None):
        """One of the buttons in the left "key" column was clicked.

        Load the information from that mapping entry into the editor.
        """
        selection_label = list_box_row.get_children()[0]
        self.active_selection_label = selection_label

        self.set_symbol(selection_label.output or "")
        self.display_key(selection_label.key)

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        mapping_list = self.get("mapping_list_advanced")
        mapping_selection = SelectionLabel()
        mapping_selection.set_label("new entry")
        mapping_selection.show_all()
        mapping_list.insert(mapping_selection, -1)

    def load_custom_mapping(self):
        # with HandlerDisabled(self.text_input, self.on_text_input_change):
        mapping_list = self.get("mapping_list_advanced")
        mapping_list.forall(mapping_list.remove)

        for key, output in custom_mapping:
            mapping_selection = SelectionLabel()
            mapping_selection.set_key(key)
            mapping_selection.set_output(output)
            mapping_selection.set_label(key.beautify())
            # Make the child label widget break lines, important for
            # long combinations
            mapping_selection.set_line_wrap(True)
            mapping_selection.set_line_wrap_mode(2)
            mapping_selection.set_justify(Gtk.Justification.CENTER)
            mapping_selection.show_all()
            mapping_list.insert(mapping_selection, -1)

        # select the first entry
        rows = mapping_list.get_children()

        if len(rows) == 0:
            self.add_empty()
            rows = mapping_list.get_children()

        mapping_list.select_row(rows[0])
        self.on_mapping_selected(list_box_row=rows[0])

    """EditableMapping"""

    def get_recording_toggle(self):
        return self.get("advanced_key_recording_toggle")

    def set_symbol(self, symbol):
        self.get("code_editor").get_buffer().set_text(symbol)

    def get_text_input(self):
        return self.get("code_editor")

    def on_text_input_change(self, _, event):
        if event.type != Gdk.EventType.KEY_RELEASE:
            # there is no "changed" event for the GtkSourceView editor
            return

        print(id(self), "on_text_input_change")
        # TODO autocompletion
        #  - also for words at the cursor position when editing a macro

        super().on_text_input_change()

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        if self.active_selection_label is None:
            return None

        return self.active_selection_label.key

    def get_symbol(self):
        """Get the assigned symbol from the middle column."""
        buffer = self.get("code_editor").get_buffer()
        symbol = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        # TODO make sure to test that this never returns ""
        return symbol if symbol else None

    def display_key(self, key):
        """Show what the user is currently pressing in ther user interface."""
        self.active_selection_label.set_label(key.beautify())

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


class AdvancedEditor(SingleEditableMapping):
    """Maintains the widgets of the advanced editor."""

    def __init__(self, user_interface):
        """TODO"""
        super().__init__(
            delete_callback=self.on_mapping_removed,
            user_interface=user_interface,
        )

        self.text_input = self.get("code_editor")
        self.text_input.connect("focus-out-event", self.on_text_input_unfocus)
        self.text_input.connect("event", self.on_text_input_change)

        self.window = self.get("window")
        self.advanced_editor = self.get("advanced_editor")
        self.timeout = GLib.timeout_add(100, self.check_add_new_key)
        self.active_key_button = None

        self.key = None

        self.get("advanced_key_recording_button").connect(
            "focus-out-event", self.on_key_recording_button_unfocus
        )

        mapping_list = self.get("mapping_list_advanced")

        if len(mapping_list.get_children()) == 0:
            self.add_empty()

        # select the first entry
        rows = mapping_list.get_children()
        first_row = rows[0]
        self.on_key_recording_button_clicked(first_row.get_children()[0])

    """SingleEditableMapping"""

    def on_text_input_change(self, _, event):
        if not event.type in [Gdk.EventType.KEY_PRESS, Gdk.EventType.KEY_RELEASE]:
            # there is no "changed" event for the GtkSourceView editor
            return

        super().on_text_input_change()

    def is_waiting_for_input(self):
        return self.get("advanced_key_recording_button").get_active()

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        return self.key

    def get_symbol(self):
        """Get the assigned symbol from the middle column."""
        buffer = self.text_input.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def display_key(self, key):
        """Show what the user is currently pressing in ther user interface."""
        self.key = key
        self.active_key_button.set_label(key.beautify())

    def put_together(self, key, symbol):
        pass

    """Editor"""

    def on_mapping_removed(self):
        """The delete button on a single mapped key was clicked."""
        # TODO
        pass

    def get(self, name):
        """Get a widget from the window"""
        return self.user_interface.builder.get_object(name)

    def consume_newest_keycode(self, key):
        """To capture events from keyboards, mice and gamepads."""
        self.switch_focus_if_complete()

        if key is None:
            return True

        if not self.is_waiting_for_input():
            return True

        self.set_key(key)

        return True

    def check_add_new_key(self):
        """If needed, add a new empty mapping to the list for the user to configure."""
        # TODO. Or a + icon to add a new one?
        pass

    def on_key_recording_button_unfocus(self, *_):
        """Don't highlight the key-recording-button anymore."""
        self.get("advanced_key_recording_button").set_active(False)

    def on_key_recording_button_clicked(self, button, symbol):
        """One of the buttons in the left "key" column was clicked.

        Load the information from that mapping entry into the editor.
        """
        self.active_key_button = button
        self.get("code_editor").get_buffer().set_text("test")
        # TODO update advanced editor widgets
        # TODO save?

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        mapping_list_advanced = self.get("mapping_list_advanced")
        key_button = Gtk.Button()
        key_button.set_label("new entry")
        key_button.show_all()
        key_button.connect(
            "clicked", lambda button: self.on_key_recording_button_clicked(button, None)
        )
        mapping_list_advanced.insert(key_button, -1)

    def load_custom_mapping(self):
        pass

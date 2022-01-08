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


"""An implementation of the editor with multiline code input and autocompletion."""


from gi.repository import Gtk, GLib, GtkSource

from inputremapper.gui.editors.base import EditableMapping
from inputremapper.gui.custom_mapping import custom_mapping
from inputremapper.gui.editors.autocompletion import Autocompletion


# TODO test


class SelectionLabel(Gtk.ListBoxRow):
    """One label per mapping in the preset.

    This wrapper serves as a storage for the information the inherited label represents.
    """

    __gtype_name__ = "SelectionLabel"

    def __init__(self):
        super().__init__()
        self.key = None

        label = Gtk.Label()

        # Make the child label widget break lines, important for
        # long combinations
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        label.set_justify(Gtk.Justification.CENTER)

        self.label = label
        self.add(label)

        self.show_all()

    def set_key(self, key):
        """Set the key this button represents

        Parameters
        ----------
        key : Key
        """
        self.key = key
        if key:
            self.label.set_label(key.beautify())
        else:
            self.label.set_label("new entry")

    def get_key(self):
        return self.key

    def set_label(self, label):
        return self.label.set_label(label)

    def __str__(self):
        return f"SelectionLabel({str(self.key)})"

    def __repr__(self):
        return self.__str__()


class Editor(EditableMapping):
    """Maintains the widgets of the editor."""

    def __init__(self, user_interface):
        self.user_interface = user_interface

        self._setup_source_view()
        self._setup_recording_toggle()

        self.window = self.get("window")
        self.timeout = GLib.timeout_add(100, self.check_add_new_key)
        self.active_selection_label = None

        selection_labels = self.get("selection_labels")
        selection_labels.connect("row-activated", self.on_mapping_selected)

        super().__init__(user_interface=user_interface)

    def _setup_recording_toggle(self):
        """Prepare the toggle button for recording key inputs."""
        toggle = self.get("key_recording_toggle")
        toggle.connect(
            "focus-out-event",
            self._show_change_key,
        )
        toggle.connect(
            "focus-in-event",
            self._show_press_key,
        )
        toggle.connect(
            "clicked",
            lambda _: (
                self._show_press_key()
                if toggle.get_active()
                else self._show_change_key()
            ),
        )

    def _show_press_key(self, *_):
        """Show user friendly instructions."""
        self.get("key_recording_toggle").set_label("Press Key")

    def _show_change_key(self, *_):
        """Show user friendly instructions."""
        self.get("key_recording_toggle").set_label("Change Key")

    def _setup_source_view(self):
        """Prepare the code editor."""
        source_view = self.get("code_editor")

        # without this the wrapping ScrolledWindow acts weird when new lines are added,
        # not offering enough space to the text editor so the whole thing is suddenly
        # scrollable by a few pixels.
        # Found this after making blind guesses with settings in glade, and then
        # actually looking at the snaphot preview! In glades editor this didn have an
        # effect.
        source_view.set_resize_mode(Gtk.ResizeMode.IMMEDIATE)

        source_view.get_buffer().connect("changed", self.line_numbers_if_multiline)

        # Syntax Highlighting
        # Thanks to https://github.com/wolfthefallen/py-GtkSourceCompletion-example
        # language_manager = GtkSource.LanguageManager()
        # fun fact: without saving LanguageManager into its own variable it doesn't work
        #  python = language_manager.get_language("python")
        # source_view.get_buffer().set_language(python)
        # TODO there are some similarities with python, but overall it's quite useless.
        #  commented out until there is proper highlighting for input-remappers syntax.

        autocompletion = Autocompletion(source_view)
        autocompletion.set_relative_to(self.get("code_editor_container"))
        autocompletion.connect("suggestion-inserted", self.save_changes)

    def line_numbers_if_multiline(self, *_):
        """Show line numbers if a macro is being edited."""
        code_editor = self.get("code_editor")
        symbol = self.get_symbol() or ""

        if "\n" in symbol:
            code_editor.set_show_line_numbers(True)
            code_editor.get_style_context().add_class("multiline")
        else:
            code_editor.set_show_line_numbers(False)
            code_editor.get_style_context().remove_class("multiline")

    def _on_delete_button_clicked(self, *_):
        """The delete button on a single mapped key was clicked."""
        super()._on_delete_button_clicked()

    def get_delete_button(self):
        return self.get("delete-mapping")

    def check_add_new_key(self):
        """If needed, add a new empty mapping to the list for the user to configure."""
        selection_labels = self.get("selection_labels")

        selection_labels = selection_labels.get_children()

        for selection_label in selection_labels:
            if selection_label.get_key() is None:
                # unfinished row found
                break
        else:
            self.add_empty()

        return True

    def on_mapping_selected(self, _=None, selection_label=None):
        """One of the buttons in the left "key" column was clicked.

        Load the information from that mapping entry into the editor.
        """
        self.active_selection_label = selection_label

        key = selection_label.key
        self.set_key(key)

        if key is None:
            self.set_symbol("")
        else:
            self.set_symbol(custom_mapping.get_symbol(key))

        self.get("window").set_focus(self.get_text_input())

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        selection_labels = self.get("selection_labels")
        mapping_selection = SelectionLabel()
        mapping_selection.set_label("new entry")
        mapping_selection.show_all()
        selection_labels.insert(mapping_selection, -1)

    def load_custom_mapping(self):
        selection_labels = self.get("selection_labels")
        selection_labels.forall(selection_labels.remove)

        for key, output in custom_mapping:
            mapping_selection = SelectionLabel()
            mapping_selection.set_key(key)
            selection_labels.insert(mapping_selection, -1)

        self.check_add_new_key()

        # select the first entry
        rows = selection_labels.get_children()

        if len(rows) == 0:
            self.add_empty()
            rows = selection_labels.get_children()

        selection_labels.select_row(rows[0])
        self.on_mapping_selected(selection_label=rows[0])

    """EditableMapping"""

    def get_recording_toggle(self):
        return self.get("key_recording_toggle")

    def set_symbol(self, symbol):
        self.get("code_editor").get_buffer().set_text(symbol or "")
        # move cursor location to the beginning, like any code editor does
        Gtk.TextView.do_move_cursor(
            self.get("code_editor"),
            Gtk.MovementStep.BUFFER_ENDS,
            -1,
            False,
        )

    def get_text_input(self):
        return self.get("code_editor")

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        if self.active_selection_label is None:
            return None

        return self.active_selection_label.key

    def get_symbol(self):
        """Get the assigned symbol from the middle column.

        If there is no symbol, this returns None. This is important for
        some other logic down the road in custom_mapping or something.
        """
        buffer = self.get("code_editor").get_buffer()
        symbol = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        return symbol

    def set_key(self, key):
        """Show what the user is currently pressing in ther user interface."""
        self.active_selection_label.set_key(key)

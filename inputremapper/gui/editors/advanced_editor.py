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


"""The advanced editor with a multiline code editor."""


from gi.repository import Gtk, GLib, GObject, GtkSource

from inputremapper.gui.editors.base import Editor, EditableMapping
from inputremapper.gui.custom_mapping import custom_mapping
from inputremapper.gui.editors.autocompletion import (
    propose_symbols,
    propose_function_names,
    get_incomplete_parameter,
    get_incomplete_function_name,
)
from inputremapper.logger import logger


# TODO test


class SelectionLabel(Gtk.Label):
    """One label per mapping in the preset.

    This wrapper serves as a storage for the information the inherited label represents.
    """

    __gtype_name__ = "Label"

    def __init__(self):
        super().__init__()
        self.key = None

        # Make the child label widget break lines, important for
        # long combinations
        self.set_line_wrap(True)
        self.set_line_wrap_mode(2)
        self.set_justify(Gtk.Justification.CENTER)
        self.show_all()

    def set_key(self, key):
        """Set the key this button represents

        Parameters
        ----------
        key : Key
        """
        self.key = key
        if key:
            self.set_label(key.beautify())
        else:
            self.set_label("new entry")

    def get_key(self):
        return self.key

    def __str__(self):
        return f"SelectionLabel({str(self.key)})"

    def __repr__(self):
        return self.__str__()


debounces = {}


def debounce(timeout):
    """Debounce a function call to improve performance."""

    def decorator(func):
        def clear_debounce(self, *args):
            debounces[func.__name__] = None
            return func(self, *args)

        def wrapped(self, *args):
            if debounces.get(func.__name__) is not None:
                GLib.source_remove(debounces[func.__name__])

            debounces[func.__name__] = GLib.timeout_add(
                timeout, lambda: clear_debounce(self, *args)
            )

        return wrapped

    return decorator


class Autocompletion(Gtk.Popover):
    """Provide keyboard-controllable beautiful autocompletions."""

    __gtype_name__ = "Popover"

    def __init__(self, text_input):
        super().__init__(
            # Don't switch the focus to the popover when it shows
            modal=False,
            # Always show the popover below the cursor, don't move it to a different
            # position based on the location within the window
            transitions_enabled=False,
        )

        self.text_input = text_input

        scrolled_window = Gtk.ScrolledWindow(
            min_content_width=200,
            max_content_height=200,
            propagate_natural_width=True,
            propagate_natural_height=True,
        )
        viewport = Gtk.Viewport()
        self.list_box = Gtk.ListBox()
        self.list_box.get_style_context().add_class("transparent")

        self.add(scrolled_window)
        scrolled_window.add(viewport)
        viewport.add(self.list_box)

        self.get_style_context().add_class("autocompletion")

        self.set_position(Gtk.PositionType.BOTTOM)

        self.show_all()

    def hide(self, *_):
        """Hide the autocompletion popover."""
        # add some delay, so that pressing the button in the completion works before
        # the popover is hidden due to focus-out-event
        GLib.timeout_add(100, self.popdown)

    def _get_text_iter_at_cursor(self):
        """Get Gtk.TextIter at the current text cursor location."""
        cursor = self.text_input.get_cursor_locations()[0]
        return self.text_input.get_iter_at_location(cursor.x, cursor.y)[1]

    def update(self, *_):
        """Find new autocompletion suggestions and display them. Hide if none."""
        if not self.text_input.is_focus():
            self.popdown()
            return

        self.list_box.forall(self.list_box.remove)

        # move the autocompletion to the text cursor
        cursor = self.text_input.get_cursor_locations()[0]
        cursor.y += 18
        self.set_pointing_to(cursor)

        text_iter = self._get_text_iter_at_cursor()
        incomplete_parameter = get_incomplete_parameter(text_iter)
        incomplete_function = get_incomplete_function_name(text_iter)
        suggested_names = propose_function_names(incomplete_function)
        suggested_names += propose_symbols(incomplete_parameter)
        suggested_names = set(suggested_names)  # get unique names

        if len(suggested_names) == 0:
            self.popdown()
            return

        self.popup()  # ffs was this hard to find

        # add visible autocompletion entries
        for name in suggested_names:
            button = Gtk.ToggleButton(label=name)
            button.connect(
                "clicked",
                # TODO make sure to test the correct button is passed
                lambda button: self._on_suggestion_clicked(text_iter, button),
            )
            button.show_all()
            self.list_box.insert(button, -1)

    def _on_suggestion_clicked(self, text_iter, button):
        """An autocompletion suggestion was selected and should be inserted.

        Parameters
        ----------
        text_iter : Gtk.TextIter
            Where to put the autocompleted word
        button : Gtk.Button
            The button that contained the autocompletion suggestion in its label
        """
        # the word the user is currently typing in
        incomplete_name = get_incomplete_function_name(text_iter)

        # the text of the autocompletion entry that was selected
        selected_proposal = button.get_label()

        if incomplete_name is None:
            # maybe the text was changed
            logger.error(
                'Failed to autocomplete "%s" with "%s"',
                incomplete_name,
                selected_proposal,
            )
            return

        # the complete current input up to the cursor
        buffer = self.text_input.get_buffer()
        left = buffer.get_text(buffer.get_start_iter(), text_iter, True)
        right = buffer.get_text(text_iter, buffer.get_end_iter(), True)

        # remove the unfinished word
        left = left[: -len(incomplete_name)]

        # insert the autocompletion
        self.text_input.get_buffer().set_text(left + selected_proposal + right)

        self.emit("suggestion-clicked")


GObject.signal_new(
    "suggestion-clicked", Autocompletion, GObject.SignalFlags.RUN_FIRST, None, []
)


class AdvancedEditor(EditableMapping, Editor):
    """Maintains the widgets of the advanced editor."""

    def __init__(self, user_interface):
        self.user_interface = user_interface

        self._setup_source_view()
        self._setup_recording_toggle()

        self.window = self.get("window")
        self.timeout = GLib.timeout_add(100, self.check_add_new_key)
        self.active_selection_label = None

        mapping_list = self.get("mapping_list_advanced")
        mapping_list.connect("row-activated", self.on_mapping_selected)

        super().__init__(user_interface=user_interface)

    def _setup_recording_toggle(self):
        """Prepare the toggle button for recording key inputs."""
        self.get("advanced_key_recording_toggle").connect(
            "focus-out-event", self.on_key_recording_button_unfocus
        )
        self.get("advanced_key_recording_toggle").connect(
            "focus-in-event",
            self.on_key_recording_button_focus,
        )

    def _setup_source_view(self):
        """Prepare the code editor."""
        source_view = self.get("code_editor")

        # Syntax Highlighting
        # Thanks to https://github.com/wolfthefallen/py-GtkSourceCompletion-example
        language_manager = GtkSource.LanguageManager()
        # fun fact: without saving LanguageManager into its own variable
        # this doesn't work
        python = language_manager.get_language("python")
        # there are some similarities with python, I don't know how I can specify
        # custom rules for input-remappers syntax.
        source_view.get_buffer().set_language(python)

        # Beautiful autocompletion using popovers
        # The one provided via source_view.get_completion() is not very appealing
        autocompletion = Autocompletion(source_view)
        autocompletion.set_relative_to(self.get("code_editor_container"))
        autocompletion.set_position(Gtk.PositionType.BOTTOM)
        autocompletion.show_all()
        autocompletion.connect("suggestion-clicked", self.save_changes)

        source_view.connect("focus-out-event", autocompletion.hide)

        source_view.get_buffer().connect(
            "changed", debounce(100)(autocompletion.update)
        )

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
        mapping_list = self.get("mapping_list_advanced")

        selection_labels = [
            selection_label.get_children()[0]
            for selection_label in mapping_list.get_children()
        ]

        for selection_label in selection_labels:
            if selection_label.get_key() is None:
                # unfinished row found
                break
        else:
            self.add_empty()

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

        key = selection_label.key
        self.set_key(key)

        if key is None:
            self.set_symbol("")
        else:
            self.set_symbol(custom_mapping.get_symbol(key))

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        mapping_list = self.get("mapping_list_advanced")
        mapping_selection = SelectionLabel()
        mapping_selection.set_label("new entry")
        mapping_selection.show_all()
        mapping_list.insert(mapping_selection, -1)

    def load_custom_mapping(self):
        mapping_list = self.get("mapping_list_advanced")
        mapping_list.forall(mapping_list.remove)

        for key, output in custom_mapping:
            mapping_selection = SelectionLabel()
            mapping_selection.set_key(key)
            mapping_selection.set_label(key.beautify())
            mapping_list.insert(mapping_selection, -1)

        self.check_add_new_key()

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
        self.get("code_editor").get_buffer().set_text(symbol or "")

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
        """Get the assigned symbol from the middle column."""
        buffer = self.get("code_editor").get_buffer()
        symbol = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        # TODO make sure to test that this never returns ""
        return symbol if symbol else None

    def set_key(self, key):
        """Show what the user is currently pressing in ther user interface."""
        self.active_selection_label.set_key(key)

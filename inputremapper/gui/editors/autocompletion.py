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


"""Autocompletion for the advanced editor."""


import re

from gi.repository import Gdk, Gtk, GLib, GObject, GtkSource

from inputremapper.system_mapping import system_mapping
from inputremapper.injection.macros.parse import FUNCTIONS
from inputremapper.injection.macros.parse import remove_comments, remove_whitespaces
from inputremapper.logger import logger


# no shorthand names
FUNCTION_NAMES = [name for name in FUNCTIONS.keys() if len(name) > 1]
# no deprecated functions
FUNCTION_NAMES.remove("ifeq")


def _get_left_text(iter):
    buffer = iter.get_buffer()
    result = buffer.get_text(buffer.get_start_iter(), iter, True)
    result = remove_comments(result)
    result = remove_whitespaces(result, '"')
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


class Autocompletion(Gtk.Popover):
    """Provide keyboard-controllable beautiful autocompletions.

    The one provided via source_view.get_completion() is not very appealing
    """

    __gtype_name__ = "Popover"

    def __init__(self, text_input):
        """Create an autocompletion popover.

        It will remain hidden until there is something to autocomplete.

        Parameters
        ----------
        text_input : Gtk.SourceView | Gtk.TextView
            The widget that contains the text that should be autocompleted
        """
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

        text_input.connect("key-press-event", self.navigate)

        self.visible = False

        self.show_all()

    def navigate(self, _, event):
        """Using the keyboard to select an autocompletion suggestion."""
        if not self.visible:
            return

        if event.keyval == Gdk.KEY_Escape:
            self.popdown()
            return

        if event.keyval not in [Gdk.KEY_Down, Gdk.KEY_Up, Gdk.KEY_Return]:
            # not one of the keys that controls the autocompletion
            return

        selected_row = self.list_box.get_selected_row()

        if event.keyval == Gdk.KEY_Return:
            if selected_row is None:
                # nothing selected, forward the event to the text editor
                return

            # a row is selected and should be used for autocompletion
            selected_row.get_children()[0].emit("clicked")
            return Gdk.EVENT_STOP

        if selected_row is None:
            # select the first row
            new_selected_row = self.list_box.get_row_at_index(0)
        else:
            # select the next row
            selected_index = selected_row.get_index()
            new_index = selected_index

            if event.keyval == Gdk.KEY_Down:
                new_index += 1

            if event.keyval == Gdk.KEY_Up:
                new_index -= 1

            new_selected_row = self.list_box.get_row_at_index(new_index)

        self.list_box.select_row(new_selected_row)

        # don't change editor contents
        return Gdk.EVENT_STOP

    def hide(self, *_):
        """Hide the autocompletion popover."""
        # add some delay, so that pressing the button in the completion works before
        # the popover is hidden due to focus-out-event
        GLib.timeout_add(100, self.popdown)

    def _get_text_iter_at_cursor(self):
        """Get Gtk.TextIter at the current text cursor location."""
        cursor = self.text_input.get_cursor_locations()[0]
        return self.text_input.get_iter_at_location(cursor.x, cursor.y)[1]

    def popup(self):
        self.visible = True
        super().popup()

    def popdown(self):
        self.visible = False
        super().popdown()

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

        self.emit("suggestion-inserted")


GObject.signal_new(
    "suggestion-inserted", Autocompletion, GObject.SignalFlags.RUN_FIRST, None, []
)

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
from inputremapper.injection.macros.parse import (
    FUNCTIONS,
    get_macro_argument_names,
    remove_comments,
    remove_whitespaces,
)
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
    #  bar(\nqux=foo
    #  bar(KEY_A,\nfoo
    #  foo
    match = re.match(rf"(?:{FUNCTION_CHAIN}|{PARAMETER}|^)(\w+)$", left_text)

    if match is None:
        return ""

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


def propose_symbols(text_iter):
    """Find key names that match the input at the cursor."""
    incomplete_name = get_incomplete_parameter(text_iter)

    if incomplete_name is None or len(incomplete_name) <= 2:
        return []

    incomplete_name = incomplete_name.lower()

    return [
        (name, name)
        for name in list(system_mapping.list_names())
        if incomplete_name in name.lower() and incomplete_name != name.lower()
    ]


def propose_function_names(text_iter):
    """Find function names that match the input at the cursor."""
    incomplete_name = get_incomplete_function_name(text_iter)

    if incomplete_name is None or len(incomplete_name) <= 1:
        return []

    incomplete_name = incomplete_name.lower()

    return [
        (name, f"{name}({', '.join(get_macro_argument_names(FUNCTIONS[name]))})")
        for name in FUNCTION_NAMES
        if incomplete_name in name.lower() and incomplete_name != name.lower()
    ]


def propose_function_parameters(text_iter):
    """Find parameter names that match the function at the cursor."""
    left_text = _get_left_text(text_iter)

    # find the current function that is being constructed
    #   "qux().foo(bar=key(), blub, 5,"
    # should result in
    #   "foo"
    function_name = ""
    brackets = 0
    i = 0
    for i in range(len(left_text) - 1, 0, -1):
        char = left_text[i]

        if char == "(" and brackets == 0:
            # the name of the function for which the parameters are being
            # autocompleted is found
            remaining = left_text[0:i]
            match = re.match(rf"(?:{FUNCTION_CHAIN}|{PARAMETER}|^)(\w+)$", remaining)

            if match is None:
                return []

            function_name = match[1]
            break

        if char == ")":
            brackets += 1

        if char == "(":
            brackets -= 1

    # get all parameter names that are already in use
    used_parameters = re.findall(r"(\w+)=", left_text[i:])

    # usually something like add_key or add_if_eq
    add_call = FUNCTIONS.get(function_name)

    if add_call is None:
        logger.debug("Unknown function %s", add_call)
        return []

    # look up possible parameters
    parameters = get_macro_argument_names(add_call)
    return [
        (f"{name}=", f"{name}=") for name in parameters if name not in used_parameters
    ]


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
            constrain_to=Gtk.PopoverConstraint.NONE,
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

        # add some delay, so that pressing the button in the completion works before
        # the popover is hidden due to focus-out-event
        text_input.connect("focus-out-event", self.on_text_input_unfocus)

        text_input.get_buffer().connect("changed", debounce(100)(self.update))

        self.set_position(Gtk.PositionType.BOTTOM)

        self.visible = False

        self.show_all()
        self.popdown()  # hidden by default. this needs to happen after show_all!

    def on_text_input_unfocus(self, *_):
        """The code editor was unfocused."""
        GLib.timeout_add(100, self.popdown)
        # "(input-remapper-gtk:97611): Gtk-WARNING **: 16:33:56.464: GtkTextView -
        # did not receive focus-out-event. If you connect a handler to this signal,
        # it must return FALSE so the text view gets the event as well"
        return False

    def navigate(self, _, event):
        """Using the keyboard to select an autocompletion suggestion."""
        if not self.visible:
            return

        if event.keyval == Gdk.KEY_Escape:
            self.popdown()
            return

        selected_row = self.list_box.get_selected_row()

        if event.keyval not in [Gdk.KEY_Down, Gdk.KEY_Up, Gdk.KEY_Return]:
            # not one of the keys that controls the autocompletion. Deselect
            # the row but keep it open
            self.list_box.select_row(None)
            return

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
        # convert it to window coords, because the cursor values will be very large
        # when the TextView is in a scrolled down ScrolledWindow.
        window_coords = self.text_input.buffer_to_window_coords(
            Gtk.TextWindowType.TEXT, cursor.x, cursor.y
        )
        cursor.x = window_coords.window_x
        cursor.y = window_coords.window_y
        cursor.y += 12
        self.set_pointing_to(cursor)

        text_iter = self._get_text_iter_at_cursor()
        suggested_names = propose_function_names(text_iter)
        suggested_names += propose_symbols(text_iter)
        suggested_names += propose_function_parameters(text_iter)

        if len(suggested_names) == 0:
            self.popdown()
            return

        self.popup()  # ffs was this hard to find

        # add visible autocompletion entries
        for name, display_name in suggested_names:
            button = Gtk.ToggleButton(label=display_name)
            button.connect(
                "clicked",
                # TODO make sure to test the correct name is passed
                lambda *_, name=name: self._on_suggestion_clicked(name),
            )
            button.show_all()
            self.list_box.insert(button, -1)

    def _on_suggestion_clicked(self, selected_proposal):
        """An autocompletion suggestion was selected and should be inserted.

        Parameters
        ----------
        selected_proposal : str
        """
        buffer = self.text_input.get_buffer()

        # make sure to replace the complete unfinished word. Look to the right and
        # remove whatever there is
        cursor_iter = self._get_text_iter_at_cursor()
        right = buffer.get_text(cursor_iter, buffer.get_end_iter(), True)
        match = re.match(r"^(\w+)", right)
        right = match[1] if match else ""
        Gtk.TextView.do_delete_from_cursor(
            self.text_input, Gtk.DeleteType.CHARS, len(right)
        )

        # do the same to the left
        cursor_iter = self._get_text_iter_at_cursor()
        left = buffer.get_text(buffer.get_start_iter(), cursor_iter, True)
        match = re.match(r".*?(\w+)$", re.sub("\n", " ", left))
        left = match[1] if match else ""
        Gtk.TextView.do_delete_from_cursor(
            self.text_input, Gtk.DeleteType.CHARS, -len(left)
        )

        # insert the autocompletion
        Gtk.TextView.do_insert_at_cursor(self.text_input, selected_proposal)

        self.emit("suggestion-inserted")


GObject.signal_new(
    "suggestion-inserted", Autocompletion, GObject.SignalFlags.RUN_FIRST, None, []
)

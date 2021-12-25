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


"""A single, configurable key mapping."""


from gi.repository import Gtk, GLib, Gdk

from keymapper.system_mapping import system_mapping
from keymapper.gui.custom_mapping import custom_mapping
from keymapper.key import Key
from keymapper.gui.reader import reader


IDLE = 0
HOLDING = 1


store = Gtk.ListStore(str)


def populate_store():
    """Fill the dropdown for key suggestions with values."""
    for name in system_mapping.list_names():
        store.append([name])

    extra = [
        "mouse(up, 1)",
        "mouse(down, 1)",
        "mouse(left, 1)",
        "mouse(right, 1)",
        "wheel(up, 1)",
        "wheel(down, 1)",
        "wheel(left, 1)",
        "wheel(right, 1)",
    ]

    for key in extra:
        # add some more keys to the dropdown list
        store.append([key])


populate_store()


class _KeycodeInput(Gtk.ToggleButton):
    """Displays instructions and the current key of a single mapping."""

    __gtype_name__ = "ToggleButton"

    def __init__(self, key):
        """

        Parameters
        ----------
        key : Key
        """
        super().__init__()

        self.key = key
        self.state = IDLE

        self.set_size_request(140, -1)

        # make the togglebutton go back to its normal state when doing
        # something else in the UI
        self.connect("focus-in-event", self.on_focus)
        self.connect("focus-out-event", self.on_unfocus)
        # don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader
        self.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)

        if key is not None:
            self.set_label(key.beautify())
        else:
            self.show_click_here()

    def on_focus(self, *_):
        """Refresh useful usage information."""
        reader.clear()
        self.show_press_key()

    def on_unfocus(self, *_):
        """Refresh useful usage information and set some state stuff."""
        self.show_click_here()
        self.set_active(False)
        self.state = IDLE

    def show_click_here(self):
        """Show 'click here' on the keycode input button."""
        if self.key is not None:
            return

        self.set_label("click here")
        self.set_opacity(0.3)

    def show_press_key(self):
        """Show 'press key' on the keycode input button."""
        if self.key is not None:
            return

        self.set_label("press key")
        self.set_opacity(1)

    def set_key(self, key):
        """Set the key and display it."""
        self.key = key
        self.set_label(key.beautify())

    def set_label(self, label):
        """Set the label of the keycode input."""
        super().set_label(label)
        # Make the child label widget break lines, important for
        # long combinations
        label = self.get_child()
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        label.set_max_width_chars(13)
        label.set_justify(Gtk.Justification.CENTER)
        self.set_opacity(1)


class Row(Gtk.ListBoxRow):
    """A single configurable key mapping of the basic editor.

    Configures an entry in custom_mapping.
    """

    __gtype_name__ = "ListBoxRow"

    def __init__(self, delete_callback, user_interface, key=None, symbol=None):
        """Construct a row widget.

        Parameters
        ----------
        key : Key
        """
        if key is not None and not isinstance(key, Key):
            raise TypeError(f"Expected key to be a Key object but got {key}")

        super().__init__()
        self.device = user_interface.group
        self.user_interface = user_interface
        self.delete_callback = delete_callback

        self.symbol_input = None
        self.keycode_input = None

        self.put_together(key, symbol)

        self.keycode_input.key = key

    def refresh_state(self):
        """Refresh the state.

        The state is needed to switch focus when no keys are held anymore,
        but only if the row has been in the HOLDING state before.
        """
        old_state = self.keycode_input.state

        if not self.keycode_input.is_focus():
            self.keycode_input.state = IDLE
            return

        unreleased_keys = reader.get_unreleased_keys()
        if unreleased_keys is None and old_state == HOLDING and self.get_key():
            # A key was pressed and then released.
            # Switch to the symbol. idle_add this so that the
            # keycode event won't write into the symbol input as well.
            window = self.user_interface.window
            GLib.idle_add(lambda: window.set_focus(self.symbol_input))

        if unreleased_keys is not None:
            self.keycode_input.state = HOLDING
            return

        self.keycode_input.state = IDLE

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        return self.keycode_input.key

    def get_symbol(self):
        """Get the assigned symbol from the middle column."""
        symbol = self.symbol_input.get_text()
        return symbol if symbol else None

    def set_key(self, new_key):
        """Check if a keycode has been pressed and if so, display it.

        Parameters
        ----------
        new_key : Key
        """
        if new_key is not None and not isinstance(new_key, Key):
            raise TypeError("Expected new_key to be a Key object")

        # the newest_keycode is populated since the ui regularly polls it
        # in order to display it in the status bar.
        previous_key = self.get_key()

        # no input
        if new_key is None:
            return

        # it might end up being a key combination
        self.keycode_input.state = HOLDING

        # keycode didn't change, do nothing
        if new_key == previous_key:
            return

        # it's legal to display the keycode

        self.keycode_input.set_key(new_key)

        symbol = self.get_symbol()

        # the symbol is empty and therefore the mapping is not complete
        if symbol is None:
            return

        # else, the keycode has changed, the symbol is set, all good
        custom_mapping.change(new_key=new_key, symbol=symbol, previous_key=previous_key)

    def on_symbol_input_change(self, _):
        """When the output symbol for that keycode is typed in."""
        key = self.get_key()
        symbol = self.get_symbol()

        if symbol is None:
            return

        if key is not None:
            custom_mapping.change(new_key=key, symbol=symbol, previous_key=None)

    def match(self, _, key, tree_iter):
        """Search the avilable names."""
        value = store.get_value(tree_iter, 0)
        return key in value.lower()

    def on_symbol_input_unfocus(self, symbol_input, _):
        """Save the preset and correct the input casing."""
        symbol = symbol_input.get_text()
        correct_case = system_mapping.correct_case(symbol)
        if symbol != correct_case:
            symbol_input.set_text(correct_case)
        self.user_interface.save_preset()

    def put_together(self, key, symbol):
        """Create all child GTK widgets and connect their signals."""
        delete_button = Gtk.EventBox()
        close_image = Gtk.Image.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        delete_button.add(close_image)
        delete_button.connect("button-press-event", self.on_delete_button_clicked)
        delete_button.set_size_request(50, -1)

        keycode_input = _KeycodeInput(key)
        self.keycode_input = keycode_input

        symbol_input = Gtk.Entry()
        self.symbol_input = symbol_input
        symbol_input.set_alignment(0.5)
        symbol_input.set_width_chars(4)
        symbol_input.set_has_frame(False)
        completion = Gtk.EntryCompletion()
        completion.set_model(store)
        completion.set_text_column(0)
        completion.set_match_func(self.match)
        symbol_input.set_completion(completion)

        if symbol is not None:
            symbol_input.set_text(symbol)

        symbol_input.connect("changed", self.on_symbol_input_change)
        symbol_input.connect("focus-out-event", self.on_symbol_input_unfocus)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_homogeneous(False)
        box.set_spacing(0)
        box.pack_start(keycode_input, expand=False, fill=True, padding=0)
        box.pack_start(symbol_input, expand=True, fill=True, padding=0)
        box.pack_start(delete_button, expand=False, fill=True, padding=0)
        box.show_all()
        box.get_style_context().add_class("row-box")

        self.add(box)
        self.show_all()

    def on_delete_button_clicked(self, *_):
        """Destroy the row and remove it from the config."""
        key = self.get_key()
        if key is not None:
            custom_mapping.clear(key)

        self.symbol_input.set_text("")
        self.keycode_input.set_label("")
        self.keycode_input.key = None
        self.delete_callback(self)

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


"""The simple editor with one row per mapping."""


from gi.repository import Gtk, GLib, Gdk

from keymapper.system_mapping import system_mapping
from keymapper.gui.custom_mapping import custom_mapping
from keymapper.key import Key
from keymapper.gui.reader import reader
from keymapper.logger import logger


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

        self.set_size_request(140, -1)

        # make the togglebutton go back to its normal state when doing
        # something else in the UI
        print('_KeycodeInput constructor connect')
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


class SingleEditableMapping:
    """A base class for editing a single mapping with a key listener and text input.

    After finishing recording keys, it will automatically focus the text input.
    """

    """To be overwritten by inheriting class"""

    def is_waiting_for_input(self):
        raise NotImplementedError

    def get_key(self):
        """Get the Key object, or None if no code is mapped on this row."""
        raise NotImplementedError

    def get_symbol(self):
        """Get the assigned symbol from the text input."""
        raise NotImplementedError

    def display_key(self, key):
        raise NotImplementedError

    def put_together(self, key, symbol):
        """Create all child GTK widgets and connect their signals."""
        raise NotImplementedError

    """Base functionality"""

    def __init__(self, delete_callback, user_interface, key=None, symbol=None):
        """Construct a row widget.

        Parameters
        ----------
        key : Key
        """
        if key is not None and not isinstance(key, Key):
            raise TypeError(f"Expected key to be a Key object but got {key}")

        self.device = user_interface.group
        self.user_interface = user_interface
        self.delete_callback = delete_callback

        self.symbol_input = None
        self.keycode_input = None

        self.put_together(key, symbol)

        self.state = IDLE

    def refresh_state(self):
        """Refresh the state.

        The state is needed to switch focus when no keys are held anymore,
        but only if the row has been in the HOLDING state before.
        """
        if not self.is_waiting_for_input():
            # TODO does it still work if I just do `if self.state == IDLE: return`?
            self.state = IDLE
            return

        old_state = self.state
        all_keys_released = reader.get_unreleased_keys() is None
        if all_keys_released and old_state == HOLDING and self.get_key():
            # A key was pressed and then released.
            # Switch to the symbol. idle_add this so that the
            # keycode event won't write into the symbol input as well.
            window = self.user_interface.window
            GLib.idle_add(lambda: window.set_focus(self.symbol_input))

        if not all_keys_released:
            self.state = HOLDING
            return

        self.state = IDLE

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
        self.state = HOLDING

        # keycode didn't change, do nothing
        if new_key == previous_key:
            return

        self.display_key(new_key)

        symbol = self.get_symbol()

        # the symbol is empty and therefore the mapping is not complete
        if symbol is None:
            return

        # else, the keycode has changed, the symbol is set, all good
        custom_mapping.change(new_key=new_key, symbol=symbol, previous_key=previous_key)

    def on_symbol_input_change(self, *_):
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

    def on_symbol_input_unfocus(self, *_):
        """Save the preset and correct the input casing."""
        symbol = self.get_symbol()
        correct_case = system_mapping.correct_case(symbol)
        if symbol != correct_case:
            self.symbol_input.set_text(correct_case)
        self.user_interface.save_preset()

    def on_keycode_input_unfocus(self, *_):
        self.state = IDLE

    def on_delete_button_clicked(self, *_):
        """Destroy the row and remove it from the config."""
        key = self.get_key()
        if key is not None:
            custom_mapping.clear(key)

        self.symbol_input.set_text("")
        self.keycode_input.set_label("")
        self.keycode_input.key = None
        self.delete_callback(self)


class Row(Gtk.ListBoxRow, SingleEditableMapping):
    """A single configurable key mapping of the basic editor.

    Configures an entry in custom_mapping.
    """

    __gtype_name__ = "ListBoxRow"

    def __init__(self, *args, **kwargs):
        Gtk.ListBoxRow.__init__(self)
        SingleEditableMapping.__init__(self, *args, **kwargs)

    def is_waiting_for_input(self):
        return self.keycode_input.is_focus()

    def get_key(self):
        """Get the Key object from the left column.

        Or None if no code is mapped on this row.
        """
        return self.keycode_input.key

    def get_symbol(self):
        """Get the assigned symbol from the middle column."""
        symbol = self.symbol_input.get_text()
        return symbol if symbol else None

    def display_key(self, key):
        self.keycode_input.set_key(key)

    def put_together(self, key, symbol):
        """Create all child GTK widgets and connect their signals."""
        delete_button = Gtk.EventBox()
        close_image = Gtk.Image.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        delete_button.add(close_image)
        delete_button.connect("button-press-event", self.on_delete_button_clicked)
        delete_button.set_size_request(50, -1)

        keycode_input = _KeycodeInput(key)
        keycode_input.connect("focus-out-event", self.on_keycode_input_unfocus)
        self.keycode_input = keycode_input
        self.keycode_input.key = key

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

        self.symbol_input.connect("changed", self.on_symbol_input_change)
        self.symbol_input.connect("focus-out-event", self.on_symbol_input_unfocus)

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


class SimpleEditor:
    """Maintains the widgets of the simple editor."""

    def __init__(self, user_interface):
        """TODO"""
        self.user_interface = user_interface
        self.window = self.get("window")
        self.timeout = GLib.timeout_add(100, self.check_add_row)

    def get(self, name):
        """Get a widget from the window"""
        return self.user_interface.builder.get_object(name)

    def load_custom_mapping(self):
        """Display the custom mapping."""
        mapping_list = self.get("mapping_list")
        mapping_list.forall(mapping_list.remove)

        for key, output in custom_mapping:
            single_key_mapping = Row(
                user_interface=self.user_interface,
                delete_callback=self.on_row_removed,
                key=key,
                symbol=output,
            )
            single_key_mapping.keycode_input.connect(
                "focus-in-event", self.user_interface.can_modify_mapping
            )
            single_key_mapping.keycode_input.connect(
                "focus-out-event", self.user_interface.save_preset
            )
            mapping_list.insert(single_key_mapping, -1)

    def get_focused_row(self):
        """Get the Row and its child that is currently in focus."""
        focused = self.window.get_focus()
        if focused is None:
            return None, None

        box = focused.get_parent()
        if box is None:
            return None, None

        row = box.get_parent()
        if not isinstance(row, Row):
            return None, None

        return row, focused

    def check_add_row(self):
        """Ensure that one empty row is available at all times."""
        rows = self.get("mapping_list").get_children()

        # verify that all mappings are displayed.
        # One of them is possibly the empty row
        num_rows = len(rows)
        num_maps = len(custom_mapping)
        if num_rows < num_maps or num_rows > num_maps + 1:
            # good for finding bugs early on during development
            logger.error(
                "custom_mapping contains %d rows, but %d are displayed",
                len(custom_mapping),
                num_rows,
            )
            logger.spam("Mapping %s", list(custom_mapping))
            logger.spam(
                "Rows    %s", [(row.get_key(), row.get_symbol()) for row in rows]
            )

        # iterating over that 10 times per second is a bit wasteful,
        # but the old approach which involved just counting the number of
        # mappings and rows didn't seem very robust.
        for row in rows:
            if row.get_key() is None or row.get_symbol() is None:
                # unfinished row found
                break
        else:
            self.add_empty()

        return True

    def consume_newest_keycode(self, key):
        """To capture events from keyboards, mice and gamepads.

        Parameters
        ----------
        key : Key or None
            If None will unfocus the input widget
        """
        # TODO highlight if a row for that key exists or something

        # inform the currently selected row about the new keycode
        row, focused = self.get_focused_row()

        if row is None:
            return True

        row.refresh_state()

        if key is None:
            return True

        if not row.keycode_input.is_focus():
            return True

        row.set_key(key)

        return True

    def clear_mapping_table(self):
        """Remove all rows from the mappings table."""
        mapping_list = self.get("mapping_list")
        mapping_list.forall(mapping_list.remove)
        custom_mapping.empty()

    def add_empty(self):
        """Add one empty row for a single mapped key."""
        empty = Row(
            user_interface=self.user_interface, delete_callback=self.on_row_removed
        )
        mapping_list = self.get("mapping_list")
        mapping_list.insert(empty, -1)

    def on_row_removed(self, single_key_mapping):
        """Stuff to do when a row was removed

        Parameters
        ----------
        single_key_mapping : Row
        """
        mapping_list = self.get("mapping_list")
        # https://stackoverflow.com/a/30329591/4417769
        mapping_list.remove(single_key_mapping)

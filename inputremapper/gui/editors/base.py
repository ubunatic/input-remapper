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


"""Base classes for all editors."""


import re

from gi.repository import Gtk, GLib, Gdk

from inputremapper.system_mapping import system_mapping
from inputremapper.gui.custom_mapping import custom_mapping
from inputremapper.key import Key
from inputremapper.logger import logger
from inputremapper.gui.reader import reader
from inputremapper.gui.utils import CTX_KEYCODE, CTX_WARNING


class EditableMapping:
    """A base class for editing a single mapping,

    Manages a text input to show the configured output, a ToggleButton to activate key
    recording and a delete button. After finishing recording keys, it will
    automatically focus the text input.

    This exists for historical reasons. If there is ever the need to implement a
    different editor this might help to get there faster. At some point there were
    two editors present and it was possible to switch between the two.
    """

    """To be overwritten by inheriting class"""

    def get_key(self):
        """Get the Key object, or None if no code is mapped on this row."""
        raise NotImplementedError

    def get_symbol(self):
        """Get the assigned symbol from the text input."""
        raise NotImplementedError

    def set_symbol(self, symbol):
        raise NotImplementedError

    def set_key(self, key):
        """Show what the user is currently pressing in ther user interface."""
        raise NotImplementedError

    def get_recording_toggle(self):
        """Return the Gtk.ToggleButton that indicates if keys are being recorded."""
        raise NotImplementedError

    def get_text_input(self):
        """Return the Gtk text input widget that contains the mappings output."""
        raise NotImplementedError

    def get_delete_button(self):
        """Return the Gtk.Button that deletes this mapping."""
        raise NotImplementedError

    """Base functionality"""

    def __init__(self, user_interface):
        """Construct an editable mapping.

        This constructor needs to be called after your inheriting object finished,
        so that the various widgets are available for event connections.
        """
        self.device = user_interface.group
        self.user_interface = user_interface

        # keys were not pressed yet
        self.input_has_arrived = False

        toggle = self.get_recording_toggle()
        toggle.connect("focus-out-event", self._reset)
        toggle.connect("focus-out-event", lambda *_: toggle.set_active(False))
        toggle.connect("focus-in-event", self.on_recording_toggle_focus)
        # Don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader. I.e. a tab input should
        # be recorded, instead of causing the recording to stop.
        toggle.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)

        text_input = self.get_text_input()
        text_input.connect("focus-out-event", self.save_changes)

        delete_button = self.get_delete_button()
        delete_button.connect("clicked", self._on_delete_button_clicked)

    def get(self, name):
        """Get a widget from the window"""
        return self.user_interface.builder.get_object(name)

    def on_recording_toggle_focus(self, *_):
        """Refresh useful usage information."""
        self._reset()
        reader.clear()
        self.user_interface.can_modify_mapping()

    def _on_delete_button_clicked(self, *_):
        """Destroy the row and remove it from the config."""
        accept = Gtk.ResponseType.ACCEPT
        if len(self.get_symbol()) > 0 and self.show_confirm_delete() != accept:
            return

        key = self.get_key()
        if key is not None:
            custom_mapping.clear(key)

        self.set_symbol("")
        self.load_custom_mapping()

    def show_confirm_delete(self):
        """Blocks until the user decided about an action."""
        confirm_delete = self.get("confirm-delete")

        text = f"Are you sure to delete this mapping?"
        self.get("confirm-delete-label").set_text(text)

        confirm_delete.show()
        response = confirm_delete.run()
        confirm_delete.hide()
        return response

    def save_changes(self, *_):
        """Save the preset and correct the input casing."""
        # correct case
        symbol = self.get_symbol()

        if not symbol:
            return

        correct_case = system_mapping.correct_case(symbol)
        if symbol != correct_case:
            self.get_text_input().get_buffer().set_text(correct_case)

        # make sure the custom_mapping is up to date
        key = self.get_key()
        if correct_case is not None and key is not None:
            custom_mapping.change(new_key=key, symbol=correct_case, previous_key=None)

        # save to disk
        self.user_interface.save_preset()

    def _is_waiting_for_input(self):
        """Check if the user is interacting with the ToggleButton for key recording."""
        return self.get_recording_toggle().get_active()

    def consume_newest_keycode(self, key):
        """To capture events from keyboards, mice and gamepads.

        Parameters
        ----------
        key : Key or None
            If None will unfocus the input widget
            # TODO wtf? _switch_focus_if_complete uses self.get_key, but
               _set_key is called after it
        """
        self._switch_focus_if_complete()

        if key is None:
            return

        if not self._is_waiting_for_input():
            return

        if key is not None and not isinstance(key, Key):
            raise TypeError("Expected new_key to be a Key object")

        # keycode is already set by some other row
        if key is not None:
            existing = custom_mapping.get_symbol(key)
            if existing is not None:
                existing = re.sub(r"\s", "", existing)
                msg = f'"{key.beautify()}" already mapped to "{existing}"'
                logger.info("%s %s", key, msg)
                self.user_interface.show_status(CTX_KEYCODE, msg)
                return True

            if key.is_problematic():
                self.user_interface.show_status(
                    CTX_WARNING,
                    "ctrl, alt and shift may not combine properly",
                    "Your system might reinterpret combinations "
                    + "with those after they are injected, and by doing so "
                    + "break them.",
                )

        # the newest_keycode is populated since the ui regularly polls it
        # in order to display it in the status bar.
        previous_key = self.get_key()

        # no input
        if key is None:
            return

        # it might end up being a key combination, wait for more
        self.input_has_arrived = True

        # keycode didn't change, do nothing
        if key == previous_key:
            logger.debug("%s didn't change", previous_key)
            return

        self.set_key(key)

        symbol = self.get_symbol()

        # the symbol is empty and therefore the mapping is not complete
        if not symbol:
            return

        # else, the keycode has changed, the symbol is set, all good
        custom_mapping.change(new_key=key, symbol=symbol, previous_key=previous_key)

    def _switch_focus_if_complete(self):
        """If keys are released, it will switch to the text_input.

        States:
        1. not doing anything, waiting for the user to start using it
        2. user focuses it, no keys pressed
        3. user presses keys
        4. user releases keys. no keys are pressed, just like in step 2, but this time
        the focus needs to switch.
        """
        if not self._is_waiting_for_input():
            self._reset()
            return

        all_keys_released = reader.get_unreleased_keys() is None
        if all_keys_released and self.input_has_arrived and self.get_key():
            # A key was pressed and then released.
            # Switch to the symbol. idle_add this so that the
            # keycode event won't write into the symbol input as well.
            window = self.user_interface.window
            GLib.idle_add(lambda: window.set_focus(self.get_text_input()))

        if not all_keys_released:
            # currently the user is using the widget, and certain keys have already
            # reached it.
            self.input_has_arrived = True
            return

        self._reset()

    def _reset(self, *_):
        self.input_has_arrived = False

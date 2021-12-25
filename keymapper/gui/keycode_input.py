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


from gi.repository import Gtk, Gdk

from keymapper.key import Key
from keymapper.gui.reader import reader


IDLE = 0
HOLDING = 1


class KeycodeInput(Gtk.ToggleButton):
    """A button that can be activated and listens for key input.

    It updates its label to show the pressed input combination.
    """

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
        self.set_label(key.beautify())

    def set_label(self, label):
        """Set the label of the keycode input."""
        super().set_label(label)
        # make the child label widget break lines, important for
        # long combinations
        label = self.get_child()
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        label.set_max_width_chars(13)
        label.set_justify(Gtk.Justification.CENTER)
        self.set_opacity(1)

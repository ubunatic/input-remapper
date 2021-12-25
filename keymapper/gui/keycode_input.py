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


import evdev
from gi.repository import Gtk, Gdk

from keymapper.system_mapping import system_mapping
from keymapper.logger import logger
from keymapper.key import Key
from keymapper.gui.reader import reader


def to_string(key):
    """A nice to show description of the pressed key."""
    if isinstance(key, Key):
        return " + ".join([to_string(sub_key) for sub_key in key])

    if isinstance(key[0], tuple):
        raise Exception("deprecated stuff")

    ev_type, code, value = key

    if ev_type not in evdev.ecodes.bytype:
        logger.error("Unknown key type for %s", key)
        return str(code)

    if code not in evdev.ecodes.bytype[ev_type]:
        logger.error("Unknown key code for %s", key)
        return str(code)

    key_name = None

    # first try to find the name in xmodmap to not display wrong
    # names due to the keyboard layout
    if ev_type == evdev.ecodes.EV_KEY:
        key_name = system_mapping.get_name(code)

    if key_name is None:
        # if no result, look in the linux key constants. On a german
        # keyboard for example z and y are switched, which will therefore
        # cause the wrong letter to be displayed.
        key_name = evdev.ecodes.bytype[ev_type][code]
        if isinstance(key_name, list):
            key_name = key_name[0]

    if ev_type != evdev.ecodes.EV_KEY:
        direction = {
            # D-Pad
            (evdev.ecodes.ABS_HAT0X, -1): "Left",
            (evdev.ecodes.ABS_HAT0X, 1): "Right",
            (evdev.ecodes.ABS_HAT0Y, -1): "Up",
            (evdev.ecodes.ABS_HAT0Y, 1): "Down",
            (evdev.ecodes.ABS_HAT1X, -1): "Left",
            (evdev.ecodes.ABS_HAT1X, 1): "Right",
            (evdev.ecodes.ABS_HAT1Y, -1): "Up",
            (evdev.ecodes.ABS_HAT1Y, 1): "Down",
            (evdev.ecodes.ABS_HAT2X, -1): "Left",
            (evdev.ecodes.ABS_HAT2X, 1): "Right",
            (evdev.ecodes.ABS_HAT2Y, -1): "Up",
            (evdev.ecodes.ABS_HAT2Y, 1): "Down",
            # joystick
            (evdev.ecodes.ABS_X, 1): "Right",
            (evdev.ecodes.ABS_X, -1): "Left",
            (evdev.ecodes.ABS_Y, 1): "Down",
            (evdev.ecodes.ABS_Y, -1): "Up",
            (evdev.ecodes.ABS_RX, 1): "Right",
            (evdev.ecodes.ABS_RX, -1): "Left",
            (evdev.ecodes.ABS_RY, 1): "Down",
            (evdev.ecodes.ABS_RY, -1): "Up",
            # wheel
            (evdev.ecodes.REL_WHEEL, -1): "Down",
            (evdev.ecodes.REL_WHEEL, 1): "Up",
            (evdev.ecodes.REL_HWHEEL, -1): "Left",
            (evdev.ecodes.REL_HWHEEL, 1): "Right",
        }.get((code, value))
        if direction is not None:
            key_name += f" {direction}"

    key_name = key_name.replace("ABS_Z", "Trigger Left")
    key_name = key_name.replace("ABS_RZ", "Trigger Right")

    key_name = key_name.replace("ABS_HAT0X", "DPad")
    key_name = key_name.replace("ABS_HAT0Y", "DPad")
    key_name = key_name.replace("ABS_HAT1X", "DPad 2")
    key_name = key_name.replace("ABS_HAT1Y", "DPad 2")
    key_name = key_name.replace("ABS_HAT2X", "DPad 3")
    key_name = key_name.replace("ABS_HAT2Y", "DPad 3")

    key_name = key_name.replace("ABS_X", "Joystick")
    key_name = key_name.replace("ABS_Y", "Joystick")
    key_name = key_name.replace("ABS_RX", "Joystick 2")
    key_name = key_name.replace("ABS_RY", "Joystick 2")

    key_name = key_name.replace("BTN_", "Button ")
    key_name = key_name.replace("KEY_", "")

    key_name = key_name.replace("REL_", "")
    key_name = key_name.replace("HWHEEL", "Wheel")
    key_name = key_name.replace("WHEEL", "Wheel")

    key_name = key_name.replace("_", " ")
    key_name = key_name.replace("  ", " ")

    return key_name


IDLE = 0
HOLDING = 1


class KeycodeInput(Gtk.ToggleButton):
    """A button that can be activated and listens for key input."""

    __gtype_name__ = "ToggleButton"

    def __init__(self, key):
        super().__init__()

        self.key = key
        self.state = IDLE

        self.set_size_request(140, -1)

        # make the togglebutton go back to its normal state when doing
        # something else in the UI
        self.connect("focus-in-event", self.on_keycode_input_focus)
        self.connect("focus-out-event", self.on_keycode_input_unfocus)
        # don't leave the input when using arrow keys or tab. wait for the
        # window to consume the keycode from the reader
        self.connect("key-press-event", lambda *args: Gdk.EVENT_STOP)

        if key is not None:
            self.set_keycode_input_label(to_string(key))
        else:
            self.show_click_here()

    def on_keycode_input_focus(self, *_):
        """Refresh useful usage information."""
        reader.clear()
        self.show_press_key()

    def on_keycode_input_unfocus(self, *_):
        """Refresh useful usage information and set some state stuff."""
        self.show_click_here()
        self.set_active(False)
        self.state = IDLE

    def show_click_here(self):
        """Show 'click here' on the keycode input button."""
        if self.key is not None:
            return

        self.set_keycode_input_label("click here")
        self.set_opacity(0.3)

    def show_press_key(self):
        """Show 'press key' on the keycode input button."""
        if self.key is not None:
            return

        self.set_keycode_input_label("press key")
        self.set_opacity(1)

    def set_keycode_input_label(self, label):
        """Set the label of the keycode input."""
        self.set_label(label)
        # make the child label widget break lines, important for
        # long combinations
        label = self.get_child()
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        label.set_max_width_chars(13)
        label.set_justify(Gtk.Justification.CENTER)
        self.set_opacity(1)

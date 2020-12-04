#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
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


"""Get stuff from /usr/share/key-mapper, depending on the prefix."""


import sys
import os
import site
import pkg_resources

from keymapper.logger import logger


logged = False


def get_data_path(filename=''):
    """Depending on the installation prefix, return the data dir.

    Since it is a nightmare to get stuff installed with pip across
    distros this is somewhat complicated. Ubuntu wants to use /usr/local
    for data_files, but not everything can be placed there.
    """
    source_path = None
    try:
        source_path = pkg_resources.require('key-mapper')[0].location
        # failed in some ubuntu installations
    except pkg_resources.DistributionNotFound:
        pass

    # depending on where this file is installed to, make sure to use the proper
    # prefix path for data
    # https://docs.python.org/3/distutils/setupscript.html?highlight=package_data#installing-additional-files # noqa pylint: disable=line-too-long

    global logged

    data_path = None
    # python3.8/dist-packages python3.7/site-packages, /usr/share,
    # /usr/local/share, endless options
    if source_path is not None:
        if '-packages' not in source_path and 'python' not in source_path:
            # probably installed with -e, running from the cloned git source
            data_path = os.path.join(source_path, 'data')
            if not os.path.exists(data_path):
                if not logged:
                    logger.debug('-e, but data missing at "%s"', data_path)
                data_path = None

    candidates = [
        '/usr/share/key-mapper',
        '/usr/local/share/key-mapper',
        os.path.join(site.USER_BASE, 'share/key-mapper'),
    ]

    if data_path is None:
        # try any of the options
        for candidate in candidates:
            if os.path.exists(candidate):
                data_path = candidate
                break

        if data_path is None:
            logger.error('Could not find the application data')
            sys.exit(1)

    if not logged:
        logger.debug('Found data at "%s"', data_path)
        logged = True

    return os.path.join(data_path, filename)

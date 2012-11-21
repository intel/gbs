# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2012 Intel, Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc., 59
# Temple Place - Suite 330, Boston, MA 02111-1307, USA.
"""Module for logging/output functionality"""

import functools
import sys
import threading

import gbp.log
from gbp.log import DEBUG, INFO, WARNING, ERROR

def waiting(func):
    """
    Function decorator to show simple waiting message for long time operations.
    """

    @functools.wraps(func)
    def _wait_with_print(*args, **kwargs):
        """Wrapper that prints dots until func finishes"""
        def _print_loop(stop, printed):
            """Main loop for dot printing thread"""
            while not stop.is_set():
                # Wait before printing to avoid output on short wait
                stop.wait(1)
                if not stop.is_set():
                    sys.stderr.write('.')
                    sys.stderr.flush()
                    printed.set()

        stop = threading.Event()
        printed = threading.Event()
        threading.Thread(target=_print_loop,
                         kwargs={'stop': stop, 'printed': printed}).start()
        try:
            return func(*args, **kwargs)
        finally:
            stop.set()
            if printed.is_set():
                sys.stderr.write('\n')

    return _wait_with_print


def setup(verbose, debug=False):
    """Basic logging setup"""

    # Change logging level names to lower case
    for level in (DEBUG, INFO, WARNING, ERROR):
        gbp.log.logging.addLevelName(level,
                                 gbp.log.logging.getLevelName(level).lower())
    # Set verbosity
    verbose = verbose or debug
    if verbose:
        LOGGER.setLevel(DEBUG)
    else:
        LOGGER.setLevel(INFO)

    # Set output format and verbosity for gbp
    if debug:
        log_fmt = '%(color)s%(name)s:%(levelname)s: %(coloroff)s%(message)s'
        gbp.log.LOGGER.setLevel(DEBUG)
    else:
        log_fmt = '%(color)s%(levelname)s: %(coloroff)s%(message)s'
    LOGGER.set_format(log_fmt)
    gbp.log.LOGGER.set_format(log_fmt)

    # Set output colors
    color_scheme = {DEBUG: gbp.log.COLORS['magenta'],
                    INFO: gbp.log.COLORS['green'],
                    WARNING: gbp.log.COLORS['yellow'],
                    ERROR: gbp.log.COLORS['red']}
    LOGGER.set_color_scheme(color_scheme)
    gbp.log.LOGGER.set_color_scheme(color_scheme)


# Module initialization
LOGGER = gbp.log.getLogger("gbs")


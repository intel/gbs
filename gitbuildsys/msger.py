#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2009, 2010, 2011 Intel, Inc.
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

import os, sys
import re
import time

__ALL__ = ['set_mode',
           'get_loglevel',
           'set_loglevel',
           'set_logfile',
           'enable_logstderr',
           'disable_logstderr',
           'raw',
           'debug',
           'verbose',
           'info',
           'warning',
           'error',
           'ask',
           'pause',
           'waiting',
           'PrintBuf',
           'PrintBufWrapper',
          ]

# COLORs in ANSI
INFO_COLOR = 32 # green
WARN_COLOR = 33 # yellow
ERR_COLOR  = 31 # red
ASK_COLOR  = 34 # blue
DEBUG_COLOR = 35 # Magenta
NO_COLOR = 0

# save the timezone info at import time
HOST_TIMEZONE = time.timezone

PREFIX_RE = re.compile('^<(.*?)>\s*(.*)', re.S)

INTERACTIVE = True

LOG_LEVEL = 1
LOG_LEVELS = {
                'quiet': 0,
                'normal': 1,
                'verbose': 2,
                'debug': 3,
                'never': 4,
             }

LOG_FILE_FP = None
LOG_CONTENT = ''
CATCHERR_BUFFILE_FD = -1
CATCHERR_BUFFILE_PATH = None
CATCHERR_SAVED_2 = -1

# save the orignal stdout/stderr at the very start
STDOUT = sys.stdout
STDERR = sys.stderr

# Configure gbp logging
import gbp.log
gbp.log.logger.format = '%(color)s%(levelname)s: %(coloroff)s%(message)s'

# Mapping for gbs->gbp log levels
GBP_LOG_LEVELS = {
                    'quiet': gbp.log.Logger.ERROR,
                    'normal': gbp.log.Logger.INFO,
                    'verbose': gbp.log.Logger.DEBUG,
                    'debug': gbp.log.Logger.DEBUG,
                    'never': gbp.log.Logger.ERROR
                 }

class PrintBuf(object):
    """Object to buffer the output of 'print' statement string
    """

    def __init__(self):
        self.buf1 = \
        self.buf2 = \
        self.old1 = \
        self.old2 = None

    def start(self):
        """Start to buffer, redirect stdout to string
        """

        if get_loglevel() != 'debug':
            import StringIO
            self.buf1 = StringIO.StringIO()
            self.buf2 = StringIO.StringIO()

            self.old1 = sys.stdout
            self.old2 = sys.stderr
            sys.stdout = self.buf1
            sys.stderr = self.buf2

    def stop(self):
        """Stop buffer, restore the original stdout, and flush the
        buffer string, return the content
        """

        if self.buf1:
            msg1 = self.buf1.getvalue().strip()
            msg2 = self.buf2.getvalue().strip()
            self.buf1.close()
            self.buf2.close()

            sys.stdout = self.old1
            sys.stderr = self.old2

            self.buf1 = \
            self.buf2 = \
            self.old1 = \
            self.old2 = None

            return (msg1, msg2)

        return ('', '')

class PrintBufWrapper(object):
    """Wrapper class for another class, to catch the print output and
    handlings.
    """

    def __init__(self, wrapped_class, msgfunc_1, msgfunc_2, *args, **kwargs):
        """Arguments:
          wrapped_class: the class to be wrapped
          msgfunc_1: function to deal with msg from stdout(1)
          msgfunc_2: function to deal with msg from stderr(2)
          *args, **kwargs: the original args of wrapped_class
        """

        self.pbuf = PrintBuf()
        self.func1 = msgfunc_1
        self.func2 = msgfunc_2

        self.pbuf.start()
        self.wrapped_inst = wrapped_class(*args, **kwargs)
        stdout_msg, stderr_msg = self.pbuf.stop()
        if stdout_msg:
            self.func1(stdout_msg)
        if stderr_msg:
            self.func2(stderr_msg)

    def __getattr__(self, attr):
        orig_attr = getattr(self.wrapped_inst, attr)
        if callable(orig_attr):
            def hooked(*args, **kwargs):
                self.pbuf.start()
                try:
                    result = orig_attr(*args, **kwargs)
                except:
                    raise
                finally:
                    stdout_msg, stderr_msg = self.pbuf.stop()
                    if stdout_msg:
                        self.func1(stdout_msg)
                    if stderr_msg:
                        self.func2(stderr_msg)

                return result

            return hooked
        else:
            return orig_attr

def _general_print(head, color, msg = None, stream = None, level = 'normal'):
    global LOG_CONTENT

    if LOG_LEVELS[level] > LOG_LEVEL:
        # skip
        return

    if stream is None:
        stream = STDOUT

    errormsg = ''
    if CATCHERR_BUFFILE_FD > 0:
        size = os.lseek(CATCHERR_BUFFILE_FD , 0, os.SEEK_END)
        os.lseek(CATCHERR_BUFFILE_FD, 0, os.SEEK_SET)
        errormsg = os.read(CATCHERR_BUFFILE_FD, size)
        os.ftruncate(CATCHERR_BUFFILE_FD, 0)

    if LOG_FILE_FP:
        if errormsg:
            LOG_CONTENT += errormsg

        if msg and msg.strip():
            timestr = time.strftime("[%m/%d %H:%M:%S] ",
                                    time.gmtime(time.time() - HOST_TIMEZONE))
            LOG_CONTENT += timestr + msg.strip() + '\n'

    if errormsg:
        _color_print('', NO_COLOR, errormsg, stream, level)

    _color_print(head, color, msg, stream, level)

def _color_print(head, color, msg, stream, _level):
    colored = True
    if color == NO_COLOR or \
       not stream.isatty() or \
       os.getenv('ANSI_COLORS_DISABLED') is not None:
        colored = False

    if head.startswith('\r'):
        # need not \n at last
        newline = False
    else:
        newline = True

    if colored:
        head = '\033[%dm%s:\033[0m ' % (color, head)
        if not newline:
            # ESC cmd to clear line
            head = '\033[2K' + head
    else:
        if head:
            head += ': '
            if head.startswith('\r'):
                head = head.lstrip()
                newline = True

    if msg is not None:
        stream.write('%s%s' % (head, msg))
        if newline:
            stream.write('\n')

    stream.flush()

def _color_perror(head, color, msg, level = 'normal'):
    if CATCHERR_BUFFILE_FD > 0:
        _general_print(head, color, msg, STDOUT, level)
    else:
        _general_print(head, color, msg, STDERR, level)

def _split_msg(head, msg):
    if isinstance(msg, list):
        msg = '\n'.join(map(str, msg))

    if msg.startswith('\n'):
        # means print \n at first
        msg = msg.lstrip()
        head = '\n' + head

    elif msg.startswith('\r'):
        # means print \r at first
        msg = msg.lstrip()
        head = '\r' + head

    match = PREFIX_RE.match(msg)
    if match:
        head += ' <%s>' % match.group(1)
        msg = match.group(2)

    return head, msg

def get_loglevel():
    return (k for k, v in LOG_LEVELS.items() if v==LOG_LEVEL).next()

def set_loglevel(level):
    global LOG_LEVEL
    if level not in LOG_LEVELS:
        # no effect
        return

    LOG_LEVEL = LOG_LEVELS[level]

    # set git-buildpackage log level
    gbp.log.logger.set_level(GBP_LOG_LEVELS[level])

def set_interactive(mode=True):
    global INTERACTIVE
    if mode:
        INTERACTIVE = True
    else:
        INTERACTIVE = False

def raw(msg=''):
    _general_print('', NO_COLOR, msg)

def info(msg):
    head, msg = _split_msg('info', msg)
    _general_print(head, INFO_COLOR, msg)

def verbose(msg):
    head, msg = _split_msg('verbose', msg)
    _general_print(head, INFO_COLOR, msg, level = 'verbose')

def warning(msg):
    head, msg = _split_msg('warning', msg)
    _color_perror(head, WARN_COLOR, msg)

def debug(msg):
    head, msg = _split_msg('debug', msg)
    _color_perror(head, DEBUG_COLOR, msg, level = 'debug')

def error(msg):
    head, msg = _split_msg('error', msg)
    _color_perror(head, ERR_COLOR, msg)
    sys.exit(1)

def waiting(func):
    """
    Function decorator to show simple waiting message for
    long time operations.
    """

    import functools

    @functools.wraps(func)
    def _wait_with_print(*args, **kwargs):
        import threading

        class _WaitingTimer(threading.Thread):
            def __init__(self):
                threading.Thread.__init__(self)
                self.event = threading.Event()
                self.waited = False

            def run(self):
                while not self.event.is_set():
                    # put the waiting above the actual
                    # printing to avoid unnecessary msg
                    self.event.wait(1)
                    if self.event.is_set():
                        break

                    self.waited = True
                    STDERR.write('.')
                    STDERR.flush()

            def stop(self):
                self.event.set()

                if self.waited:
                    STDERR.write('\n')
                    STDERR.flush()

        timer = _WaitingTimer()
        timer.start()

        try:
            out = func(*args, **kwargs)
        except:
            raise
        finally:
            timer.stop()

        return out

    return _wait_with_print

def ask(msg, default=True):
    _general_print('\rQ', ASK_COLOR, '')
    try:
        if default:
            msg += '(Y/n) '
        else:
            msg += '(y/N) '
        if INTERACTIVE:
            while True:
                repl = raw_input(msg)
                if repl.lower() == 'y':
                    return True
                elif repl.lower() == 'n':
                    return False
                elif not repl.strip():
                    # <Enter>
                    return default

                # else loop
        else:
            if default:
                msg += ' Y'
            else:
                msg += ' N'
            _general_print('', NO_COLOR, msg)

            return default
    except KeyboardInterrupt:
        sys.stdout.write('\n')
        sys.exit(2)

def pause(msg=None):
    if INTERACTIVE:
        _general_print('\rQ', ASK_COLOR, '')
        if msg is None:
            msg = 'press <ENTER> to continue ...'
        raw_input(msg)

def set_logfile(fpath):
    global LOG_FILE_FP

    def _savelogf():
        if LOG_FILE_FP:
            if not os.path.exists(os.path.dirname(LOG_FILE_FP)):
                os.makedirs(os.path.dirname(LOG_FILE_FP))
            fhandle = open(LOG_FILE_FP, 'w')
            fhandle.write(LOG_CONTENT)
            fhandle.close()

    if LOG_FILE_FP is not None:
        warning('duplicate log file configuration')

    LOG_FILE_FP = os.path.abspath(os.path.expanduser(fpath))

    import atexit
    atexit.register(_savelogf)

def enable_logstderr(fpath):
    global CATCHERR_BUFFILE_FD
    global CATCHERR_BUFFILE_PATH
    global CATCHERR_SAVED_2

    if os.path.exists(fpath):
        os.remove(fpath)
    CATCHERR_BUFFILE_PATH = fpath
    CATCHERR_BUFFILE_FD = os.open(CATCHERR_BUFFILE_PATH, os.O_RDWR|os.O_CREAT)
    CATCHERR_SAVED_2 = os.dup(2)
    os.dup2(CATCHERR_BUFFILE_FD, 2)

def disable_logstderr():
    global CATCHERR_BUFFILE_FD
    global CATCHERR_BUFFILE_PATH
    global CATCHERR_SAVED_2

    raw(msg=None) # flush message buffer and print it
    os.dup2(CATCHERR_SAVED_2, 2)
    os.close(CATCHERR_SAVED_2)
    os.close(CATCHERR_BUFFILE_FD)
    os.unlink(CATCHERR_BUFFILE_PATH)
    CATCHERR_BUFFILE_FD = -1
    CATCHERR_BUFFILE_PATH = None
    CATCHERR_SAVED_2 = -1

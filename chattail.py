#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2013 Freaxmind
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__  = 'Freaxmind'
__email__   = 'freaxmind@freaxmind.pro'
__version__ = '0.1'
__license__ = 'GPLv3'

"""
    Chattail: Tail your log over XMPP

    See the file LICENSE for copying permission.
"""

import ConfigParser
import sleekxmpp
import threading
import argparse
import logging
import sys
import os


# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout, we will set the default encoding to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')


class ChattailException(Exception):
    """Exception specific to chattail"""
    def __init__(self, message, user_message=None):
        # NOTE: do not display confidential informations (like paths and configurations) to a chat user !!!
        Exception.__init__(self, message)   # to log and monitor
        self.user_message = user_message    # to send to the chat client


class Chattail(sleekxmpp.ClientXMPP):
    """Chattail is a XMPP bot to consult your log with a chat client
    Usage: <command> <arg1> <arg2> ...
    """

    def __init__(self, config_file):
        """
        Initialize:
            - program: logger/config reader
            - xmpp: client/event handlers
            - bot: files/help
        """
        # init logger
        self.logger = logging.getLogger('chattail')
        self.logger.info('Initializing: logger ...')
        self.logger.info('\t- logging level set to %s', logging.getLevelName(self.logger.getEffectiveLevel()))

        # init config
        self.logger.info('Initializing: configuration parser ...')
        if not os.path.isfile(config_file):
            raise ChattailException("The configuration file does not exist: %s" % config_file)
        self.config = ConfigParser.ConfigParser()
        self.config.read(config_file)
        self.logger.info('\t- configuration file is: %s' % config_file)

        # init client
        self.logger.info('Initializing: XMPP client ...')
        self.my_jid = self.config.get('Credentials', 'jid')
        my_password = self.config.get('Credentials', 'password')
        sleekxmpp.ClientXMPP.__init__(self, self.my_jid, my_password)

        # init event handlers
        self.logger.info('Initializing: event handlers ...')
        self.add_event_handler("message", self.__message_handler)
        self.add_event_handler("session_start", self.__start_handler)
        self.add_event_handler("disconnected", self.__disconnect_handler)
        self.add_event_handler("presence_available", self.__presence_handler)
        self.add_event_handler("presence_unavailable", self.__presence_handler)

        # init files
        self.logger.info('Initializing: log files')
        self.files = dict(self.config.items('Files'))
        self.running = {}           # jid => file
        for fn, fp in self.files.items():
            self.logger.info('\t- %s => %s' % (fn, fp))

        # init help
        self.logger.info('Initializing: helper ...')
        self.helps = {}     # command => doc
        self.helps['ls'] = self.__action_ls.__doc__
        self.helps['tail'] = self.__action_tail.__doc__
        self.helps['stop'] = self.__action_stop.__doc__
        self.helps['help'] = self.__action_help.__doc__

    def run(self):
        """Main process: handle client command"""
        self.logger.info('Connecting ...')
        if self.connect():
            self.logger.info('Processing ...')
            self.process(block=True)
        else:
            raise ChattailException('Unable to connect with the XMPP Server')

    def dispatch(self, from_jid, action, args):
        """Call the method associated to the action"""

        if action == 'ls':
            self.__spawn_thread(self.__action_ls, from_jid, args)
        elif action == 'tail':
            self.__spawn_thread(self.__action_tail, from_jid, args)
        elif action == 'stop':
            self.__spawn_thread(self.__action_stop, from_jid, args)
        elif action == 'help':
            self.__spawn_thread(self.__action_help, from_jid, args)
        else:
            raise ChattailException("Unknown action '%s' send by '%s'" % (action, from_jid),
                                    "Unknown action '%s' (type 'help' to list all command)" % action)

    def parse_command(self, from_jid, msg):
        """Parse a message and return an action + args"""
        msg = msg.strip()

        # errors
        if len(msg) == 0:
            raise ChattailException("Command sent by %s is empty (only whitespaces)" % from_jid,
                                    "Command empty (only whitespaces)")

        # split the command
        words = msg.split(' ')
        action = words[0]
        args = words[1:] if len(words) > 1 else []

        return action, args

    def is_my_contact(self, jid, and_online=False):
        """Check if a JID is in my contact list (optional: and online)"""
        if not jid in self.contacts:
            return False

        if and_online and not jid in self.onlines:
            return False

        return True

    def send_warning(self, jid, exception, then_raise=True):
        """
        Helper: send a warning to a chat client
        NOTE: exception raised in a thread will not be catch by the thread caller
        """
        self.logger.warn(exception.message)
        self.send_message(mto=jid, mbody=exception.user_message)

        # stop the thread
        if then_raise:
            raise exception

    def __action_ls(self, jid, args):
        """
        List all the file you can tail
        Usage: ls
        """
        self.logger.info("Ls action initialized by '%s'" % jid)

        filenames = ["- %s" %k for k in self.files.keys()]
        self.send_message(mto=jid, mbody="List of files:\n%s" % '\n'.join(filenames))

    def __action_tail(self, jid, args):
        """
        Display the last line of a file (like tail -f on a UNIX system)
        Usage: tail filename

        Arguments:
            - filename: name of the file. Type 'ls' to list the file you can tail.
        """
        from time import sleep
        import subprocess

        # errors
        if len(args) != 1:
            e = ChattailException("Command Error from '%s': tail command takes only 1 arg (%d given)" % (jid, len(args)),
                                  "Command Error: tail command takes only 1 arg (%d given)" % (len(args)))
            self.send_warning(jid, e)

        filename = args[0]

        if not filename in self.files.keys():
            e = ChattailException("Command Error from '%s': filename '%s' is not tailable" % (jid, filename),
                                  "Command Error: filename '%s' is not tailable. Type 'ls' to list all tailable files." % (filename))
            self.send_warning(jid, e)
        if not os.path.isfile(self.files[filename]):
            e = ChattailException("Command Error from '%s': filename '%s' is missing" % (jid, filename))
            self.send_message(mto=jid, mbody="Command Error: filename '%s' is missing." % (filename))
            self.send_warning(jid, e)
        if jid in self.running.keys():
            self.send_message(mto=jid, mbody="Tail is currently running. Type 'stop'.")
            return

        # create a subprocess
        self.logger.info("Tail action of '%s' initialized by '%s'" % (filename, jid))
        p = subprocess.Popen(["tail", "-f", self.files[filename]], stdout=subprocess.PIPE)
        self.running[jid] = filename

        # tail !
        while jid in self.running.keys():
            line = p.stdout.readline()
            self.send_message(mto=jid, mbody=line)
            if not line:
                sleep(1)

    def __action_stop(self, jid, args):
        """
        Stop your current tail
        Usage: stop
        """
        # errors
        if not jid in self.running.keys():
            self.send_message(mto=jid, mbody="No tail is running")
            return

        self.logger.info("Tail action of '%s' stopped by '%s'" % (self.running[jid], jid))
        self.send_message(mto=jid, mbody="Tail successfully stopped")
        del(self.running[jid])

    def __action_help(self, jid, args):
        """
        Display the documentation
        Usage: help command?

        Arguments:
            - command: name of the command.

        Type 'help' to list all the available command
        """

        if len(args) == 1:
            action = args[0]

            if action in self.helps.keys():
                self.logger.info("Help action '%s' action initialized by '%s'" % (action, jid))
                self.send_message(mto=jid, mbody=self.helps[action])
            else:
                e = ChattailException("Help not found for command '%s' initialized by '%s'" % (action, jid),
                                      "Command Error: there is no help for '%s'.\nType 'help' to list all available command" % action)
                self.send_warning(jid, e)
        else:
            self.logger.info("Help action *all* initialized by '%s'" % jid)
            self.send_message(mto=jid, mbody=self.__doc__ + '\nCommands:\n'
                              + '\n'.join(['\t- %s' % k for k in self.helps.keys()]))

    def __spawn_thread(self, fct, *args):
        """Helper: spawn a thread for an action method"""
        t = threading.Thread(target=fct, name=fct.__name__, args=args)
        t.start()

    def __start_handler(self, event):
        """Process the session_start event"""
        # init rooster
        self.logger.info('Initializing: roster ...')
        self.send_presence()
        self.get_roster()

        # init internal contact list
        self.logger.info('Initializing: internal contact list ...')
        self.contacts = [v for k,v in self.config.items('Contacts')]
        self.onlines = []

    def __disconnect_handler(self, nothing):
        """Process incoming disconnect event"""
        # TODO: os._exit is a little abrupt ... any suggestion ?
        self.logger.info("Stopping all operation (%d pending) ..." % len(self.running))
        for k in self.running.keys():
            del(self.running[k])

        self.logger.info('Good bye :)')

    def __presence_handler(self, presence):
        """Process incoming presence stanzas"""
        from_jid = presence['from'].bare

        # errors
        if from_jid == self.my_jid or not self.is_my_contact(from_jid):
            return

        # switch between online/offline
        if not 'type' in presence.keys() or presence['type'] == 'available':
            logging.info('Now online: %s', from_jid)
            self.onlines.append(from_jid)
        elif presence['type'] == 'unavailable':
            logging.info('Now offline %s', from_jid)
            self.onlines.remove(from_jid)

    def __message_handler(self, msg):
        """Process incoming message stanzas"""
        from_jid = msg['from'].bare

        # errors
        if not msg['type'] in ('chat', 'normal'):
            logging.warn('Message from %s ignored (msg.type=%s)', (from_jid, ['type']))
            return
        if not self.is_my_contact(from_jid, and_online=True):
            logging.warn('Message from %s ignored (not my contact or offline)' % from_jid)
            return

        # dispatch the command
        try:
            action, args = self.parse_command(from_jid, msg['body'])
            self.dispatch(from_jid, action, args)
        except ChattailException as e:
            self.send_warning(from_jid, e, then_raise=False)




if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Tail your log over XMPP")
    parser.add_argument('-c', '--config', default='prod.conf', help="Path to your configuration file (format: .ini)")
    parser.add_argument('-v', '--verbose', help='set the logger level to VERBOSE', action='store_const', dest='loglevel', const=logging.INFO)
    args = parser.parse_args(sys.argv[1:])

    # Set the logging level and format
    loglevel = args.loglevel if args.loglevel else logging.WARNING
    logging.basicConfig(level=loglevel, format='%(levelname)-8s %(message)s')

    # Initialize the client
    tails = Chattail(args.config)
    tails.run()

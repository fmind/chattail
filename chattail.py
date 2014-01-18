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
    Chattail: Tail your Syslog over XMPP

    See the file LICENSE for copying permission.
"""

import ConfigParser
import sleekxmpp
import argparse
import logging
import sys
import os


# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout SleekXMPP, we will set the default encoding
# ourselves to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')


class ChattailException(Exception):
    """Exception class: for all exceptions specific to chattail"""
    pass

class Chattail(sleekxmpp.ClientXMPP):
    """Main class: Log handler + XMPP Client"""

    def __init__(self, config_file):
        """
        Initialize:
            - logging
            - configuration
            - XMPP client
            - XMPP events
        """
        # init logger
        self.logger = logging.getLogger('chattail')
        self.logger.info('Logging level set to: %s', logging.getLevelName(self.logger.getEffectiveLevel()))

        # init config
        self.logger.info('Initializing: configuration parser ...')
        if not os.path.isfile(config_file):
            raise ChattailException("Config file does not exist: %s" % config_file)
        self.config = ConfigParser.ConfigParser()
        self.config.read(config_file)

        self.logger.info('Initializing: XMPP client ...')
        # init client
        jid = self.config.get('Credentials', 'jid')
        password = self.config.get('Credentials', 'password')
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        # init plugins
        self.logger.info('Initializing: XMPP plugins ...')
        #self.register_plugin('xep_0060') # PubSub

        # init events
        self.logger.info('Initializing: XMPP events ...')
        self.add_event_handler("session_start", self.__start_handler)
        self.add_event_handler("message", self.__message_handler)
        self.add_event_handler("presence_available", self.__presence_handler)
        self.add_event_handler("presence_unavailable", self.__presence_handler)

    def run(self):
        """Main process: handle bot commands"""
        self.logger.info('Connecting ...')
        if self.connect():
            self.logger.info('Processing ...')
            self.process(block=True)
        else:
            raise ChattailException('Unable to connect with XMPP Server')

    def parse_command(self, msg):
        """Parse a message into a command + args"""
        words = msg.split(' ')
        action = words[0]
        args = words[1:] if len(words) > 1 else []

        if len(action) == 0:
            raise ChattailException("Command empty")

        return action, args

    def dispatch(self, from_jid, action, args):
        """Send an action to the right method"""
        if action == 'tail':
            self.__tail(from_jid, args)

    def __tail(self, jid, args):
        from time import sleep
        while True:
            self.send_message(mto=jid, mbody="Coucou")
            sleep(1)

    def __start_handler(self, event):
        """
        Process the session_start event.

        Arguments:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        """
        self.send_presence()
        self.get_roster()

        # init contact list
        self.contacts = [v for k,v in self.config.items('Contacts')]
        self.onlines = []

    def __message_handler(self, msg):
        """
        Process incoming message stanzas.

        Arguments:
            msg -- The received message stanza.
        """
        from_jid = msg['from'].bare
        if not msg['type'] in ('chat', 'normal') and not self.is_my_contact(msg['from'].bare, and_online=True):
            return

        action, args = self.parse_command(msg['body'])
        self.dispatch(from_jid, action, args)
        msg.reply("Thanks for sending\n%(body)s" % msg).send()

    def __presence_handler(self, presence):
        """
        Process incoming presence stanzas.

        Arguments:
            presence -- The received presence stanza.
        """
        from_jid = presence['from'].bare

        # only for the contact list specified
        if not self.is_my_contact(from_jid):
            return

        if not 'type' in presence.keys() or presence['type'] == 'available':
            self.onlines.append(from_jid)
            logging.info('Now online: %s', from_jid)
        elif presence['type'] == 'unavailable':
            self.onlines.remove(from_jid)
            logging.info('Now offline %s', from_jid)

    def is_my_contact(self, jid, and_online=False):
        """Check if a JID is in my contact/online list"""
        if and_online and jid in self.onlines:
            return True
        elif not and_online and jid in self.contacts:
            return True


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Tail your Syslog over XMPP")
    parser.add_argument('-c', '--config', default='prod.conf', help="Path to your configuration file (format: .ini)")
    parser.add_argument('-d', '--debug', help='set logging to DEBUG', action='store_const', dest='loglevel', const=logging.DEBUG)
    parser.add_argument('-verbose', '--verbose', help='set logging to VERBOSE', action='store_const', dest='loglevel', const=logging.INFO)
    args = parser.parse_args(sys.argv[1:])

    # Setup logging
    loglevel = args.loglevel if args.loglevel else logging.WARNING
    logging.basicConfig(level=loglevel, format='%(levelname)-8s %(message)s')

    # Init client
    tails = Chattail(args.config)
    tails.run()

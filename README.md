chattail
========

Chattail is a bot that allows you to monitor your log with a simple XMPP chat client ([full list](https://encrypted.google.com/search?hl=en&q=xmpp%20client)).

This program is functional, but I haven’t test it in a production environment.

>> Use it with caution, but tweak it as you like (see the LICENCE file).

## Why ?
* **Net traversal**: launch the bot on your server, monitor your log everywhere.
* **Fast monitoring**: connect with a chat client, and check your log in secs.
* **Restricted access**: give a read access only to the file your wish to share (ex: apache access).
* **Multi-user**: add one line to your configuration file, and a new admin can check the log.
* **XMPP coolness**: XMPP is a great protocol (extensible, multi-purpose, well designed ...).

## Installation
* **Install the dependencies**: sleekxmpp, dnspython, pyasn1, pyasn1-modules.
* **Create 2 XMPP accounts**: one for the bot, the other for your chat client.
* **Edit your configuration file**: copy the test.sample.conf file and edit your account/files.
* **Launch the program**: simply type 'python chattail.py -c test.conf' with an system account that can access the file.

## Usage

When the program is launched, the JID associated with the bot will appear online. Simply pass your command just like a Command Line Interface:
* ls
* help
* help tail
* tail messages
* stop

Use the 'help' action to get more information about the command you wish you use. It's straightforward !

## For developers

This section will explain the design:

Why use XMPP and not start a new protocol from scratch ?
XMPP is extensible and come with a lot a functionality and software (client/server). It's an open standard, so we don't have to reinvent the wheel.

Why Python ?
It's a popular, mature and easy to use language. SleekXMPP is a well designed library (thanks [Fritzy](https://github.com/fritzy/SleekXMPP).

Why only one big Python file ?
It's easier that way. Download the file, edit a configuration file and run the program !

Why threads other processes ?
I don't need big computation, but sharing memory was necessary (even though the stopping condition can be improved).

Why there is no unit tests ?
It's hard (although possible) to test an asynchronous client/software program. If you need to debug chattail, just give the -v (verbose) to turn the console display (It can give you a lot of information).

If you have more questions, don't hesitate to contact me !

## Plans

* **Support plugins**: add custom command to make it an extensible bot.
* **More configuration**: output log file, file permissions, resource ID ...
* **Multiple tail per JID**: this can be messy, it need a careful planning.
* **More security**: I try to make as many internal test as I can, but there is still room to improvment.

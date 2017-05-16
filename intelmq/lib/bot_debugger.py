# -*- coding: utf-8 -*-
"""
Utilities for debugging intelmq bots.

BotDebugger is called via intelmqctl. It starts a live running bot instance,
leverages logging to DEBUG level and permits even a non-skilled programmer
who may find themselves puzzled with Python nuances and server deployment twists
to see what's happening in the bot and where's the error.

Depending on the subcommand received, the class either
 * starts the bot as is (default)
 * processes single message, either injected or from default pipeline (process subcommand)
 * reads the message from input pipeline or send a message to output pipeline (message subcommand)
"""
import logging
import json
from pprint import pprint

from importlib import import_module
from intelmq.lib.utils import StreamHandler, error_message_from_exc
from intelmq.lib.message import Event, MessageFactory


class BotDebugger:
        def leverageLogger(self, level=logging.DEBUG):
            self.instance.logger.setLevel(level)
            for h in self.instance.logger.handlers:
                if isinstance(h, StreamHandler):
                    h.setLevel(level)

        def __init__(self, module_path, bot_id, run_subcommand=None, console_type=None, dryrun=None, message_kind=None, msg=None):
            module = import_module(module_path)
            bot = getattr(module, 'BOT')
            self.instance = bot(bot_id)
            self.leverageLogger()

            if not run_subcommand:
                self.instance.start()
            else:
                self.instance._Bot__connect_pipelines()
                if run_subcommand == "process":
                    self._process(dryrun, msg)
                elif run_subcommand == "message":
                    # XXX self.leverageLogger(level=logging.INFO)
                    self._message(message_kind, msg)
                elif run_subcommand == "console":
                    self._console(console_type)
                else:
                    print("Subcommand {} not known.".format(run_subcommand))

        class PoorBot:
            pass

        def _console(self,console_type):
            consoles = [console_type, "ipdb", "pudb", "pdb"]
            for console in consoles:                
                try:
                    module = import_module(console)
                except Exception as exc:                    
                    pass
                else:
                    if console_type and console != console_type:
                        print("Console {} not available.".format(console_type))
                    print("*** Using console {}. Please use 'self' to access to the bot instance properties. ***".format(module.__name__))
                    break
            else:
                print("Can't run console.")
                return

            self = self.instance
            module.set_trace()

        def _message(self, message_action_kind, msg):
            if message_action_kind == "get":
                self.instance.logger.info("Trying to get the message...")
                # never pops from source to internal queue, thx to disabling brpoplpush operation
                pl = self.instance._Bot__source_pipeline                
                pl.pipe.brpoplpush = lambda source_q, inter_q, i: pl.pipe.lindex(source_q, -1)                
                pprint(self.instance.receive_message())
            elif message_action_kind == "pop":
                self.instance.logger.info("Trying to pop the message...")
                pprint(self.instance.receive_message())
                self.instance.acknowledge_message()
            elif message_action_kind == "send":                
                if msg:
                    try:
                        msg = MessageFactory.unserialize(msg)
                    except (Exception, KeyError, TypeError, json.JSONDecodeError) as exc:                        
                        print("Message can not be parsed from JSON: " + error_message_from_exc(exc))
                        return
                    self.instance.send_message(msg)
                    self.instance.logger.info("Message sent to output pipelines.")
                else:
                    self.instance.logger.info("Message missing!")

        def _process(self, dryrun, msg):
            if msg:
                self.instance._Bot__source_pipeline.receive = lambda: msg
                self.instance.logger.info("Message from cli will be used when processing.")

            if dryrun:
                self.instance.send_message = lambda msg: self.instance.logger.info("DRYRUN: Message would be sent now!")
                self.instance.acknowledge_message = lambda: self.instance.logger.info("DRYRUN: Message would be acknowledged now!")
                print("Dryrun only, no message will be really sent through.")

            self.instance.logger.info("Processing...")
            self.instance.process()
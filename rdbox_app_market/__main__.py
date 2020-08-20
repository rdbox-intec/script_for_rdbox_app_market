#!/usr/bin/env python3
import os
import logging
import rdbox_app_market.config
from rdbox_app_market.group_write_rotating_fileHandler import GroupWriteRotatingFileHandler
from rdbox_app_market.mission_control import MissionControl
from logging import getLogger, StreamHandler, Formatter

r_logger = getLogger('rdbox_cli')
r_print = getLogger('rdbox_cli').getChild("stdout")


def r_logger_setup():
    # r_logger
    r_logger = getLogger('rdbox_cli')
    r_logger.setLevel(logging.DEBUG)
    users = "%s/%s" % (os.environ['SUDO_USER'], os.environ['USER']) if 'SUDO_USER' in os.environ else os.environ['USER']
    handler_format = Formatter(
        fmt='%(asctime)s - {users} - %(process)d - %(levelname)s - %(message)s'.format(users=users), datefmt='%Y-%m-%dT%H:%M:%S%z')
    file_path = rdbox_app_market.config.get("rdbox", "log_path")
    file_handler = GroupWriteRotatingFileHandler(
        filename=file_path, maxBytes=10 * 1024 * 1024, backupCount=10)
    file_handler.setLevel(
        getattr(logging, rdbox_app_market.config.get("rdbox", "log_level")))
    file_handler.setFormatter(handler_format)
    r_logger.addHandler(file_handler)
    # r_print
    r_print = getLogger('rdbox_cli').getChild("stdout")
    r_print.setLevel(logging.DEBUG)
    handler_format = Formatter('%(message)s')
    stream_handler = StreamHandler()
    stream_handler.setLevel(
        getattr(logging, rdbox_app_market.config.get("rdbox", "out_level")))
    stream_handler.setFormatter(handler_format)
    r_print.addHandler(stream_handler)


def launch():
    MissionControl.launch()


if __name__ == '__main__':
    r_logger_setup()
    r_print.info("[rdbox_app_market] Start.")
    launch()
    r_print.info("[rdbox_app_market] End.")
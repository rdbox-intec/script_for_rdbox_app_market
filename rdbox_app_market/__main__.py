#!/usr/bin/env python3
import sys
import logging
import argparse
import rdbox_app_market.config
from rdbox_app_market.group_write_rotating_fileHandler import GroupWriteRotatingFileHandler
from rdbox_app_market.mission_control import VendorMissionControl, RDBOXMissionControl
from logging import getLogger, StreamHandler, Formatter

r_logger = getLogger('rdbox_cli')
r_print = getLogger('rdbox_cli').getChild("stdout")


def r_logger_setup():
    # r_logger
    r_logger = getLogger('rdbox_cli')
    r_logger.setLevel(logging.DEBUG)
    handler_format = Formatter(
        fmt='%(asctime)s - %(process)d - %(levelname)s - %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
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


def launch(type: str, exec_publish: bool):
    ret = False
    if type == 'bot-gen':
        ret = VendorMissionControl.launch(exec_publish)
    elif type == 'manually':
        ret = RDBOXMissionControl.launch(exec_publish)
    else:
        r_print.error("argment error.")
    return ret


def main():
    # logging
    r_logger_setup()
    r_print.info("[rdbox_app_market] Start.")
    # args
    parser = argparse.ArgumentParser(description='RDBOX service.')
    parser.add_argument('type', help='bot-gen OR manually')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    r_logger.info("ARGS: {args}".format(args=args))
    # launch
    ret = launch(args.type, args.publish)
    return ret


if __name__ == '__main__':
    ret = main()
    # End
    r_print.info("[rdbox_app_market] End.")
    if ret:
        sys.exit(0)
    else:
        sys.exit(1)

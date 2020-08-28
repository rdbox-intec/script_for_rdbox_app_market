#!/usr/bin/env python3
# coding: utf-8

import os
import configparser

DEFAULT_CONFIG_FILE = os.environ.get(
    'RDBOX_APP_MARKET_CONF', 'rdbox_app_market.conf')


class ConfigUtil(object):
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read(DEFAULT_CONFIG_FILE)


_util = ConfigUtil()


def get(section, key):
    return _util.config.get(section, key)

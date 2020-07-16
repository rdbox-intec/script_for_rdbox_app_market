#!/usr/bin/env python3
from rdbox_app_market.util import Util


def test_has_key_recursion():
    data = {'1st': {'2nd': {'3rd': 'TEST'}}}
    assert Util.has_key_recursion(data, '1st') == data['1st']                # {'2nd': {'3rd': 'TEST'}}
    assert Util.has_key_recursion(data, '2nd') == data['1st']['2nd']         # {'3rd': 'TEST'}
    assert Util.has_key_recursion(data, '3rd') == 'TEST'                     # TEST
    assert Util.has_key_recursion(data, '4th') is None

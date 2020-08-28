#!/usr/bin/env python3
from rdbox_app_market.util import Util


def test_has_key_recursion():
    data = {'1st': {'2nd': {'3rd': 'TEST'}}}
    assert Util.has_key_recursion(data, '1st') == data['1st']                # {'2nd': {'3rd': 'TEST'}}
    assert Util.has_key_recursion(data, '2nd') == data['1st']['2nd']         # {'3rd': 'TEST'}
    assert Util.has_key_recursion(data, '3rd') == 'TEST'                     # TEST
    assert Util.has_key_recursion(data, '4th') is None


def test_has_key_recursion_full():
    data = {'one': {'2nd': {'3rd': 'HOGE'}}, 'two': {'2nd': {'3rd': 'FUGE'}}}
    assert Util.has_key_recursion_full(data, '2nd') == {'_.one': {'3rd': 'HOGE'}, '_.two': {'3rd': 'FUGE'}}
    assert Util.has_key_recursion_full(data, '3rd') == {'_.one.2nd': 'HOGE', '_.two.2nd': 'FUGE'}
    assert Util.has_key_recursion_full(data, '4th') == {}

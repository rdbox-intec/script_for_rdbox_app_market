#!/usr/bin/env python3

class Util(object):
    @classmethod
    def has_key_recursion(cls, obj, key):
        if key in obj:
            return obj[key]
        for k, v in obj.items():
            if isinstance(v, dict):
                item = cls.has_key_recursion(v, key)
                if item is not None:
                    return item

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

    @classmethod
    def has_key_recursion_full(cls, obj, key, now=['_']):
        fields_found = {}
        for k, v in obj.items():
            if k == key:
                keyword = '.'.join(now)
                fields_found.setdefault(keyword, v)
            elif isinstance(v, dict):
                _now = []
                _now.extend(now)
                _now.append(k)
                results = cls.has_key_recursion_full(v, key, _now)
                for struct, result in results.items():
                    fields_found.setdefault(struct, result)
        return fields_found

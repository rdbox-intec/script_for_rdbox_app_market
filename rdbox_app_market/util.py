#!/usr/bin/env python3

class Util(object):
    @classmethod
    def has_key_recursion(cls, obj: dict, key: str) -> any:
        """Returns the value of the first key found in the dictionary. (No recursive search is performed.)

        Args:
            obj (dict): target
            key (str): key

        Returns:
            dict: value of key
        """
        if key in obj:
            return obj[key]
        for k, v in obj.items():
            if isinstance(v, dict):
                item = cls.has_key_recursion(v, key)
                if item is not None:
                    return item

    @classmethod
    def has_key_recursion_full(cls, obj: dict, key: str, now=['_']) -> dict:
        """Scans the received dict object for full value and returns the value specified by key.

        The key in the return value indicates the layer. The "_" is the top layer. (Default)
        Dot-separated characters indicate a layer.

        example_dict = {'one': {'two': 'three'}, '1': {'two': '3'}}

        has_key_recursion_full(example_dict, 'one')
        >>> {'_': {'two': 'three'}}
        has_key_recursion_full(example_dict, '1')
        >>> {'_': {'two': '3'}}
        has_key_recursion_full(example_dict, 'two')
        >>> {'_.one': 'three', '_.1': '3'}

        Args:
            obj (dict): target
            key (str): key
            now (list, optional): String prefix for the top layer. Defaults to ['_'].

        Returns:
            dict: A dict that is key for layer info string and this value(any type)
        """
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

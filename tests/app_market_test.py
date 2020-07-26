#!/usr/bin/env python3
from rdbox_app_market.app_market import RequirementObject


class TestRequirementObject(object):
    def test_getter(self):
        data = RequirementObject('postgresql', '8.x.x', 'https://charts.bitnami.com/bitnami', 'postgresql.enabled')
        assert data.get_name() == 'postgresql'
        assert data.get_version() == '8.x.x'
        assert data.get_repository() == 'https://charts.bitnami.com/bitnami'
        assert data.get_condition() == 'postgresql.enabled'
        assert data.get_tags() is None

    def test_repr(self, capfd):
        data = RequirementObject('postgresql', '8.x.x', 'https://charts.bitnami.com/bitnami', 'postgresql.enabled')
        print(data)
        out, _ = capfd.readouterr()
        assert out == "<RequirementObject 'postgresql' : '8.x.x' : 'https://charts.bitnami.com/bitnami' : 'postgresql.enabled' : 'None'>\n"

#!/usr/bin/env python3
from rdbox_app_market.helm import HelmCommand


def test_init(mocker):
    mocker.patch('platform.system').return_value = 'Linux'
    helm_command = HelmCommand()
    assert helm_command.helm == '/snap/bin/helm'

    mocker.patch('platform.system').return_value = 'Darwin'
    helm_command = HelmCommand()
    assert helm_command.helm == '/usr/local/bin/helm'

    mocker.patch('platform.system').return_value = 'Windows'
    helm_command = HelmCommand()
    assert helm_command.helm == 'helm'

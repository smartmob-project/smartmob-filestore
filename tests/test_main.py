# -*- coding: utf-8 -*-


import pytest
import subprocess

from smartmob_filestore import version


@pytest.mark.parametrize('command', [
    ['smartmob-filestore', '--version'],
    ['python', '-m', 'smartmob_filestore', '--version'],
])
def test_version(command):
    output = subprocess.check_output(command)
    assert output.decode('utf-8').strip() == version

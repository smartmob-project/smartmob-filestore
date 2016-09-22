# -*- coding: utf-8 -*-


import aiohttp
import asyncio
import json
import os
import pytest
import subprocess
import signal

from smartmob_filestore import main, version
from timeit import default_timer
from unittest import mock


@pytest.mark.parametrize('command', [
    ['smartmob-filestore', '--version'],
    ['python', '-m', 'smartmob_filestore', '--version'],
])
def test_version(command):
    output = subprocess.check_output(command)
    assert output.decode('utf-8').strip() == version


@pytest.mark.asyncio
async def test_main_logging_arg(event_loop, unused_tcp_port_factory,
                                tempdir, fluent_server):
    """Logging endpoint can be specified on the command-line."""

    # Start the server.
    #
    # TODO: make sure this is cleaned up correctly on test failure!
    host = '127.0.0.1'
    port = unused_tcp_port_factory()
    task = event_loop.create_task(main([
        '--host=%s' % host,
        '--port=%d' % port,
        '--logging-endpoint=fluent://%s:%d/smartmob-filestore' % (
            fluent_server[0],
            fluent_server[1],
        ),
    ], loop=event_loop))

    async with aiohttp.ClientSession(loop=event_loop) as client:
        url = 'http://%s:%d' % (host, port)

        # Confirm that the server is listening.
        ref = default_timer()
        now = default_timer()
        while (now - ref) < 5.0:
            try:
                async with client.get(url) as response:
                    assert response.status == 403
                break
            except aiohttp.errors.ClientOSError:
                await asyncio.sleep(0.1)
            now = default_timer()

    # Stop the server.
    os.kill(os.getpid(), signal.SIGINT)
    await task

    # Access should have been logged.
    print(fluent_server[2])
    assert fluent_server[2] == [
        [b'smartmob-filestore.http.access', mock.ANY, {
            b'@timestamp': mock.ANY,
            b'request': mock.ANY,
            b'duration': mock.ANY,
            b'outcome': 403,
            b'path': b'/',
        }],
    ]


@pytest.mark.asyncio
async def test_main_logging_env(event_loop, unused_tcp_port_factory,
                                tempdir, fluent_server, save_env):
    """Logging endpoint can be specified using an environment variable."""

    os.environ['SMARTMOB_LOGGING_ENDPOINT'] = \
        'fluent://%s:%d/smartmob-filestore' % fluent_server[0:2]

    # Start the server.
    #
    # TODO: make sure this is cleaned up correctly on test failure!
    host = '127.0.0.1'
    port = unused_tcp_port_factory()
    task = event_loop.create_task(main([
        '--host=%s' % host,
        '--port=%d' % port,
    ], loop=event_loop))

    async with aiohttp.ClientSession(loop=event_loop) as client:
        url = 'http://%s:%d' % (host, port)

        # Confirm that the server is listening.
        ref = default_timer()
        now = default_timer()
        while (now - ref) < 5.0:
            try:
                async with client.get(url) as response:
                    assert response.status == 403
                break
            except aiohttp.errors.ClientOSError:
                await asyncio.sleep(0.1)
            now = default_timer()

    # Stop the server.
    os.kill(os.getpid(), signal.SIGINT)
    await task

    # Access should have been logged.
    print(fluent_server[2])
    assert fluent_server[2] == [
        [b'smartmob-filestore.http.access', mock.ANY, {
            b'@timestamp': mock.ANY,
            b'request': mock.ANY,
            b'duration': mock.ANY,
            b'outcome': 403,
            b'path': b'/',
        }],
    ]


@pytest.mark.asyncio
async def test_main_logging_std(event_loop, unused_tcp_port_factory,
                                tempdir, capsys):
    """Logging endpoint defaults to standard output."""

    assert not os.environ.get('SMARTMOB_LOGGING_ENDPOINT')

    # Start the server.
    #
    # TODO: make sure this is cleaned up correctly on test failure!
    host = '127.0.0.1'
    port = unused_tcp_port_factory()
    task = event_loop.create_task(main([
        '--host=%s' % host,
        '--port=%d' % port,
    ], loop=event_loop))

    async with aiohttp.ClientSession(loop=event_loop) as client:
        url = 'http://%s:%d' % (host, port)

        # Confirm that the server is listening.
        ref = default_timer()
        now = default_timer()
        while (now - ref) < 5.0:
            try:
                async with client.get(url) as response:
                    assert response.status == 403
                break
            except aiohttp.errors.ClientOSError:
                await asyncio.sleep(0.1)
            now = default_timer()

    # Stop the server.
    os.kill(os.getpid(), signal.SIGINT)
    await task

    # Access should have been logged.
    out, err = capsys.readouterr()
    assert err == ''
    assert out
    out = [line.strip() for line in out.split('\n')]
    out = [json.loads(line) for line in out if line]
    assert out == [
        {
            'event': 'http.access',
            '@timestamp': mock.ANY,
            'request': mock.ANY,
            'duration': mock.ANY,
            'outcome': 403,
            'path': '/',
        },
        {
            'event': 'stop',
            '@timestamp': mock.ANY,
        },
    ]

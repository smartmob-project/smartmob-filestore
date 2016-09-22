# -*- coding: utf-8 -*-


import asyncio
import aiohttp
import os
import pytest
import signal

from smartmob_filestore import main
from timeit import default_timer


@pytest.mark.asyncio
async def test_upload_and_download(event_loop, unused_tcp_port_factory,
                                   tempdir):
    """Uploaded files can be downloaded again."""

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
        url = 'http://%s:%d/%s' % (host, port, 'hello.txt')

        # Upload the file.
        #
        # NOTE: it may take a moment for the server to become ready.
        ref = default_timer()
        now = default_timer()
        while (now - ref) < 5.0:
            try:
                async with client.put(url, data=b'Hello, world!') as response:
                    assert response.status == 201
                break
            except aiohttp.errors.ClientOSError:
                await asyncio.sleep(0.1)
            now = default_timer()

        # Download it back.
        async with client.get(url) as response:
            assert response.status == 200
            content = await response.read()

    # Stop the server.
    os.kill(os.getpid(), signal.SIGINT)
    await task

    # Make sure we got what we uploaded.
    assert content == b'Hello, world!'

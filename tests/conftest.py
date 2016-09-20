# -*- coding: utf-8 -*-

import aiotk
import msgpack
import os
import os.path
import pytest
import testfixtures

from smartmob_filestore import configure_logging


__here__ = os.path.dirname(os.path.abspath(__file__))


@pytest.yield_fixture(scope='function')
def tempdir():
    old_cwd = os.getcwd()
    with testfixtures.TempDirectory(create=True) as directory:
        os.chdir(directory.path)
        yield
        os.chdir(old_cwd)
        directory.cleanup()


@pytest.fixture(scope='function', autouse=True)
def logging():
    """Setup default logging for tests.

    Tests can reconfigure logging if they wish to.
    """
    configure_logging(
        log_format='kv',
        utc=False,
        endpoint='file:///dev/stdout',
    )


async def service_fluent_client(records, reader, writer):
    """TCP handler for mock FluentD server.

    See:
    - https://github.com/fluent/fluentd/wiki/Forward-Protocol-Specification-v0
    - https://pythonhosted.org/msgpack-python/api.html#msgpack.Unpacker
    """
    unpacker = msgpack.Unpacker()
    data = await reader.read(1024)
    while data:
        unpacker.feed(data)
        for record in unpacker:
            records.append(record)
        data = await reader.read(1024)


@pytest.yield_fixture(scope='function')
def fluent_server(event_loop, unused_tcp_port_factory):
    """Mock FluentD server."""

    records = []

    # TODO: provide a built-in means to pass in shared server state as this
    #       wrapper will probably not cancel cleanly.
    async def service_connection(reader, writer):
        return await service_fluent_client(records, reader, writer)

    # Serve connections.
    host = '127.0.0.1'
    port = unused_tcp_port_factory()
    server = aiotk.TCPServer(host, port, service_connection)
    server.start()
    event_loop.run_until_complete(server.wait_started())
    yield host, port, records
    server.close()
    event_loop.run_until_complete(server.wait_closed())

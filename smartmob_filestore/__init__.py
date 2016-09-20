# -*- coding: utf-8 -*-


import aiohttp.web
import aiotk
import argparse
import asyncio
import fluent.sender
import timeit
import sys
import pkg_resources
import structlog
import uuid
import os

from datetime import datetime, timezone
from urllib.parse import urlsplit


version = pkg_resources.resource_string('smartmob_filestore', 'version.txt')
version = version.decode('utf-8').strip()
"""Package version (as a dotted string)."""


cli = argparse.ArgumentParser(description="Run the HTTP file server.")
cli.add_argument('--version', action='version', version=version,
                 help="Print version and exit.")
cli.add_argument('--host', action='store', dest='host',
                 type=str, default='0.0.0.0')
cli.add_argument('--port', action='store', dest='port',
                 type=int, default=8080)
cli.add_argument('--logging-endpoint', action='store', dest='logging_endpoint',
                 default=None)
cli.add_argument('--storage', action='store', dest='storage',
                 type=str, default='.')


class FluentLoggerFactory:
    """For use with ``structlog.configure(logger_factory=...)``."""

    @classmethod
    def from_url(cls, url):
        parts = urlsplit(url)
        if parts.scheme != 'fluent':
            raise ValueError('Invalid URL: "%s".' % url)
        if parts.query or parts.fragment:
            raise ValueError('Invalid URL: "%s".' % url)
        netloc = parts.netloc.rsplit(':', 1)
        if len(netloc) == 1:
            host, port = netloc[0], 24224
        else:
            host, port = netloc
            try:
                port = int(port)
            except ValueError:
                raise ValueError('Invalid URL: "%s".' % url)
        return FluentLoggerFactory(parts.path[1:], host, port)

    def __init__(self, app, host, port):
        self._app = app
        self._host = host
        self._port = port
        self._sender = fluent.sender.FluentSender(app, host=host, port=port)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def app(self):
        return self._app

    def __call__(self):
        return FluentLogger(self._sender)


class FluentLogger:
    """Structlog logger that sends events to FluentD."""

    def __init__(self, sender):
        self._sender = sender

    def info(self, event, **kwds):
        self._sender.emit(event, kwds)


class TimeStamper(object):
    """Custom implementation of ``structlog.processors.TimeStamper``.

    See:
    - https://github.com/hynek/structlog/issues/81
    """

    def __init__(self, key, utc):
        self._key = key
        self._utc = utc
        if utc:
            def now():
                return datetime.utcnow().replace(tzinfo=timezone.utc)
        else:
            def now():
                return datetime.now()
        self._now = now

    def __call__(self, _, __, event_dict):
        timestamp = event_dict.get('@timestamp')
        if timestamp is None:
            timestamp = self._now()
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        event_dict['@timestamp'] = timestamp
        return event_dict


def configure_logging(log_format, utc, endpoint):
    processors = [
        TimeStamper(
            key='@timestamp',
            utc=utc,
        ),
    ]
    if endpoint.startswith('file://'):
        path = endpoint[7:]
        if path == '/dev/stdout':
            stream = sys.stdout
        elif path == '/dev/stderr':
            stream = sys.stderr
        else:
            stream = open(path, 'w')
        logger_factory = structlog.PrintLoggerFactory(file=stream)
        if log_format == 'kv':
            processors.append(structlog.processors.KeyValueRenderer(
                sort_keys=True,
                key_order=['@timestamp', 'event'],
            ))
        else:
            processors.append(structlog.processors.JSONRenderer(
                sort_keys=True,
            ))
    elif endpoint.startswith('fluent://'):
        utc = True
        logger_factory = FluentLoggerFactory.from_url(endpoint)
    else:
        raise ValueError('Invalid logging endpoint "%s".' % endpoint)
    structlog.configure(
        processors=processors,
        logger_factory=logger_factory,
    )


async def inject_request_id(app, handler):
    """aiohttp middleware: ensures each request has a unique request ID.

    See: ``inject_request_id``.
    """

    async def trace_request(request):
        request['x-request-id'] = \
            request.headers.get('x-request-id') or str(uuid.uuid4())
        return await handler(request)

    return trace_request


async def echo_request_id(request, response):
    """aiohttp signal: ensures each response contains the request ID.

    See: ``echo_request_id``.
    """
    response.headers['x-request-id'] = request.get('x-request-id', '?')


async def access_log_middleware(app, handler):
    """Log each request in structured event log."""

    event_log = app.get('smartmob.event_log') or structlog.get_logger()
    clock = app.get('smartmob.clock') or timeit.default_timer

    # Keep the request arrival time to ensure we get intuitive logging of
    # events.
    arrival_time = datetime.utcnow().replace(tzinfo=timezone.utc)

    async def access_log(request):
        ref = clock()
        try:
            response = await handler(request)
            event_log.info(
                'http.access',
                path=request.path,
                outcome=response.status,
                duration=(clock()-ref),
                request=request.get('x-request-id', '?'),
                **{'@timestamp': arrival_time},
            )
            return response
        except aiohttp.web.HTTPException as error:
            event_log.info(
                'http.access',
                path=request.path,
                outcome=error.status,
                duration=(clock()-ref),
                request=request.get('x-request-id', '?'),
                **{'@timestamp': arrival_time},
            )
            raise
        except Exception:
            event_log.info(
                'http.access',
                path=request.path,
                outcome=500,
                duration=(clock()-ref),
                request=request.get('x-request-id', '?'),
                **{'@timestamp': arrival_time},
            )
            raise

    return access_log


class HTTPServer:
    """Run an aiohttp application as an asynchronous context manager."""

    def __init__(self, app, host='0.0.0.0', port=80, loop=None):
        self._app = app
        self._loop = loop or asyncio.get_event_loop()
        self._handler = app.make_handler()
        self._server = None
        self._host = host
        self._port = port

    async def __aenter__(self):
        assert not self._server
        self._server = await self._loop.create_server(
            self._handler, self._host, self._port,
        )

    async def __aexit__(self, *args):
        assert self._server
        self._server.close()
        await self._server.wait_closed()
        await self._app.shutdown()
        await self._handler.finish_connections(1.0)
        await self._app.cleanup()
        self._server = None


async def upload(request):
    """Naive file upload."""
    storage = request.app['smartmob.storage']
    path = os.path.join(storage, request.match_info['path'])
    data = await request.read()
    with open(path, 'wb') as stream:
        stream.write(data)
    return aiohttp.web.Response(status=201, headers={
        'x-request-id': request.headers.get('x-request-id', '?'),
    })


async def main(argv, loop=None):
    """Run the HTTP file server."""

    arguments = cli.parse_args(argv)

    # Send structured logs to requested destination.
    configure_logging(
        log_format='iso',
        utc=True,
        endpoint=arguments.logging_endpoint,
    )
    event_log = structlog.get_logger()

    # Pick the event loop.
    loop = loop or asyncio.get_event_loop()

    # Prepare a web application.
    app = aiohttp.web.Application(
        loop=loop,
        middlewares=[
            inject_request_id,
            access_log_middleware,
        ],
    )
    app.on_response_prepare.append(echo_request_id)

    # Define routes.
    app.router.add_static('/', arguments.storage)
    app.router.add_route('PUT', '/{path:.+}', upload)

    # Inject context.
    app['smartmob.event_log'] = event_log
    app['smartmob.clock'] = timeit.default_timer
    app['smartmob.storage'] = arguments.storage

    # Serve requests.
    done = asyncio.Future(loop=loop)
    with aiotk.handle_ctrlc(done, loop=loop):
        async with HTTPServer(app, arguments.host, arguments.port):
            await done

    # Shut down.
    event_log.info('stop')


if __name__ == '__main__':  # pragma: no cover
    loop = asyncio.get_event_loop()
    sys.exit(loop.run_until_complete(
        main(sys.argv[1:], loop=loop)
    ))

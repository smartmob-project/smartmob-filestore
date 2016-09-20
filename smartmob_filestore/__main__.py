# -*- coding: utf-8 -*-


import asyncio
import sys

from smartmob_filestore import main


# NOTE: contents are tested in sub-process.  Coverage will ignore this file, so
#       keep its contents to a minimum.


def entry_point():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(
        main(sys.argv[1:], loop=loop)
    )


# Required for `python -m smartmob_filestore ...`.
if __name__ == '__main__':
    sys.exit(entry_point())

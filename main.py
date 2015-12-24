import asyncio
import functools
import sys
import time

from PyQt4.QtGui import QProgressBar, QApplication
from quamash import QEventLoop, QThreadExecutor


@asyncio.coroutine
def master(progress):
    yield from first_50(progress)
    loop = asyncio.get_event_loop()
    with QThreadExecutor(1) as executor:
        yield from loop.run_in_executor(executor, functools.partial(last_50, progress, loop))


@asyncio.coroutine
def first_50(progress):
    for i in range(50):
        progress.setValue(i)
        yield from asyncio.sleep(.1)


def last_50(progress, loop):
    for i in range(50, 100):
        loop.call_soon_threadsafe(progress.setValue, i)
        time.sleep(.1)


def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    progress = QProgressBar()
    progress.setRange(0, 99)
    progress.show()

    with loop:
        loop.run_until_complete(master(progress))

if __name__ == '__main__':
    main()
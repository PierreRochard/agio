import asyncio
import sys
import time

from PyQt4.QtGui import QProgressBar, QApplication
from quamash import QEventLoop, QThreadExecutor


@asyncio.coroutine
def master():
    yield from first_50()
    with QThreadExecutor(1) as executor:
        yield from loop.run_in_executor(executor, last_50)


@asyncio.coroutine
def first_50():
    for i in range(50):
        progress.setValue(i)
        yield from asyncio.sleep(.1)


def last_50():
    for i in range(50, 100):
        loop.call_soon_threadsafe(progress.setValue, i)
        time.sleep(.1)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    progress = QProgressBar()
    progress.setRange(0, 99)
    progress.show()

    with loop:
        loop.run_until_complete(master())
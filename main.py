import asyncio
import functools
import sys
import time

from PyQt4 import QtGui
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
        loop.call_soon_threadsafe(progress. setValue, i)
        time.sleep(.1)


class MainWindow(QtGui.QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.progress = QtGui.QProgressBar(self)
        self.progress.setRange(0, 99)
        self.setGeometry(300, 300, 250, 150)
        self.setWindowTitle('Agio')
        self.show()


def main():
    app = QtGui.QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    main_window = MainWindow()
    with loop:
        loop.run_until_complete(master(main_window.progress))
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

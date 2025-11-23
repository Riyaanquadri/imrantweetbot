import signal
from .scheduler import BotScheduler
from .logger import logger
from .config import Config


def main():
    logger.info('Starting Crypto AI Twitter Bot')
    sched = BotScheduler()
    sched.start()

    def _stop(signum, frame):
        logger.info('Shutting down...')
        sched.shutdown()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    # keep alive
    try:
        while True:
            signal.pause()
    except KeyboardInterrupt:
        _stop(None, None)

if __name__ == '__main__':
    main()

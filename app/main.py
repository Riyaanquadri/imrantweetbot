import signal
from .scheduler import BotScheduler
from .logger import logger
from .config import Config
from app.src.db import init_db


def main():
    # Ensure the lite audit DB used by helper utilities is initialized.
    init_db()
    # Validate configuration before startup
    if not Config.validate():
        logger.error('Configuration validation failed. Please check your .env file or secret store.')
        exit(1)
    
    logger.info('Starting Crypto AI Twitter Bot')
    logger.info(f'Bot handle: {Config.BOT_HANDLE}')
    logger.info(f'Project keywords: {Config.PROJECT_KEYWORDS}')
    logger.info(f'DRY_RUN mode: {Config.DRY_RUN}')
    
    sched = BotScheduler()
    sched.start()

    def _stop(signum, frame):
        logger.info('Shutting down...')
        sched.shutdown()
        exit(0)

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

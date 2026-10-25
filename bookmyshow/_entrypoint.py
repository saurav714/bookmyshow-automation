
from asyncio import get_event_loop

from ._context import BookMyShowAutomation


def entrypoint():
    show = BookMyShowAutomation()
    loop = get_event_loop()

    try:
        loop.run_until_complete(show.start())
    except KeyboardInterrupt:
        loop.run_until_complete(show.stop())

    loop.close()


if __name__ == "__main__":
    entrypoint()

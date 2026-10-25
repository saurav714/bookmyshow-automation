
from ._entrypoint import entrypoint
from ._logging import _init_logging

__debugmode__ = True

_init_logging(debug=__debugmode__)

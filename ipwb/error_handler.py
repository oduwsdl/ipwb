import functools
import logging
from typing import Callable

logger = logging.getLogger('ipwb')


def exception_logger(catch=True, exception_class=Exception):
    """
    Decorator that catches exceptions in the function and logs them.

    Usage:

    ```python
    @exception_logger()
    def decorated_function(foo, bar):
        do_something
    ```

    `exception_logger()` will catch any exception that happens in
    `decorated_function()` while it is being executed, and log an error using
    Python built in `logging` library.

    Unless `catch` argument is `False` - in which case, the exception will be
    reraised.
    """
    def decorator(f: Callable):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)

            except exception_class as err:
                if catch:
                    logger.critical(str(err))

                else:
                    raise

        return wrapper

    return decorator

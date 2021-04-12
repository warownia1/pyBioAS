import enum
import fcntl
import functools
import itertools
import os
import sys
import warnings
from collections import OrderedDict

import yaml.resolver

try:
    import simplejson as json
except ImportError:
    import json


class Singleton(type):
    """
    A metaclass that prevents instantiation of the object more than once.
    The object is created and cached the first time the constructor is called.
    Subsequent constructor calls return the same object making it a singleton.
    """
    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        return cls.__instances[cls]

    @property
    def instance(cls):
        return cls()


class LimitedSizeDict(OrderedDict):
    """
    A dictionary containing a limited number of entries.
    If more entries then specified by ``max_size`` are added,
    the oldest ones are removed.
    """
    def __init__(self, max_size, mapping=None):
        super().__init__(mapping or {})
        self.max_size = max_size

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if len(self) > self.max_size:
            del self[next(self.__iter__())]

    def update(self, mapping=None, **kwargs):
        super().update(mapping or {}, **kwargs)
        if len(self) > self.max_size:
            for key in list(itertools.islice(self, len(self) - self.max_size)):
                del self[key]


class BackoffCounter:
    """
    A counter that exponentially increases the waiting duration every failure.
    The counter's next value indicates the skipped attempts before the
    operation should be re-tried. If the operation fails, ``failure`` method
    should be called to called to increment the counter, otherwise the
    counter will reset the next iteration as if the operation succeeded.
    """
    _zero_gen = itertools.repeat(0)

    def __init__(self, max_tries=64):
        """
        :param max_tries: Number of attempts before giving up.
        """
        self._counter = self._zero_gen
        self._tries = 0
        self.max_tries = max_tries
        self.current = 0

    def __next__(self):
        try:
            self.current = next(self._counter)
        except StopIteration:
            self.reset()
            self.current = next(self._counter)
        return self.current

    def __iter__(self):
        return self

    @property
    def give_up(self):
        """ Indicates whether the max attempts has been reached. """
        return self._tries >= self.max_tries

    def next(self):
        """
        Returns the remaining delay

        The operation should be retried when this function returns 0.
        Calling it after successful attempt (not followed by a
        ``failure`` call) resets the counter.
        """
        return self.__next__()

    def failure(self):
        """ Should be called when the operation fails. """
        self._tries = min(self.max_tries, self._tries + 1)
        self.current = 1 << self._tries
        self._counter = reversed(range(self.current))

    def reset(self):
        """ Resets the counter. """
        self._counter = self._zero_gen
        self._tries = 0
        self.current = 0


try:
    from functools import cached_property
except ImportError:
    # noinspection PyPep8Naming
    class cached_property:
        """ A data descriptor delaying field initialization and caching the value. """
        def __init__(self, initializer):
            self._init = initializer

        def __get__(self, instance, owner):
            if instance is None:
                return self
            val = self._init(instance)
            name = self._init.__name__
            if name.startswith('__') and not name.endswith('__'):
                name = '_' + owner.__name__ + name
            instance.__dict__[name] = val
            return val


# noinspection PyPep8Naming
class class_property:
    """A data descriptor allowing properties on class instances."""
    def __init__(self, getter):
        if not isinstance(getter, (classmethod, staticmethod)):
            getter = classmethod(getter)
        self._getter = getter

    def __get__(self, instance, owner):
        return self._getter.__get__(instance, owner)()


try:
    from contextlib import nullcontext
except ImportError:
    class nullcontext:
        def __init__(self, enter_result=None):
            self.enter_result = enter_result

        def __enter__(self):
            return self.enter_result

        def __exit__(self, *excinfo):
            pass


def deprecated(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        warnings.simplefilter('always', DeprecationWarning)
        warnings.warn(
            "Function %s is deprecated" % func.__name__,
            DeprecationWarning, stacklevel=2
        )
        warnings.simplefilter('default', DeprecationWarning)
        return func(*args, **kwargs)
    return wrapper


class SafeTranscludingOrderedYamlLoader(yaml.SafeLoader):
    def __init__(self, stream):
        try:
            self.root_path = os.path.dirname(stream.name)
        except AttributeError:
            self.root_path = os.path.curdir
        self.root_path = os.path.abspath(self.root_path)
        super().__init__(stream)


def _include_constructor(loader: SafeTranscludingOrderedYamlLoader, node: yaml.Node):
    val = loader.construct_scalar(node)
    val = val.replace('#', '::', 1).split('::', 1)
    fn, path = val if len(val) == 2 else (val[0], '/')
    fn = os.path.join(loader.root_path, fn)
    with open(fn) as f:
        obj = yaml.load(f, Loader=loader.__class__)
    for key in filter(None, path.split('/')):
        obj = obj[key]
    return obj


if sys.version_info < (3, 7):
    # in python 3.7 onwards, regular dictionaries are ordered.
    def _mapping_constructor(loader, node):
        loader.flatten_mapping(node)
        return OrderedDict(loader.construct_pairs(node))

    SafeTranscludingOrderedYamlLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _mapping_constructor
    )

SafeTranscludingOrderedYamlLoader.add_constructor(
    '!include', _include_constructor
)


class JobStatus(enum.IntEnum):
    PENDING = 1  # Request submitted to the database but not processed yet
    REJECTED = 2  # Request rejected due to input parameter limitations
    ACCEPTED = 3  # Job was accepted but has not been sent to the queuing system yet
    QUEUED = 4  # Job successfully submitted to the queuing system
    RUNNING = 5  # Job is being executed
    COMPLETED = 6  # Job finished successfully with 0 status code
    INTERRUPTED = 7  # Job has been interrupted during execution
    DELETED = 8  # Job has been deleted from the queuing system
    FAILED = 9  # Job finished with non-0 status code
    ERROR = 10  # Internal error
    UNKNOWN = 11
    CANCELLING = 12  # Job is in progress of being cancelled

    def is_finished(self):
        return self in (
            JobStatus.REJECTED, JobStatus.COMPLETED, JobStatus.INTERRUPTED,
            JobStatus.DELETED, JobStatus.FAILED, JobStatus.ERROR
        )


class PidFile:
    # licensed under the MIT license. by Graham Poulter
    # http://code.activestate.com/recipes/577911/
    """Context manager that locks a pid file.  Implemented as class
    not generator because daemon.py is calling .__exit__() with no parameters
    instead of the None, None, None specified by PEP-343."""
    def __init__(self, path):
        self.path = path
        self.pidfile = None

    def __enter__(self):
        pidfile = self.pidfile = open(self.path, 'a+')
        fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        pidfile.seek(0)
        pidfile.truncate()
        pidfile.write(str(os.getpid()))
        pidfile.flush()
        pidfile.seek(0)
        return pidfile

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        try:
            self.pidfile.close()
        except OSError as e:
            if e.errno != 9:
                raise
        os.remove(self.path)


def daemonize():
    """ Daemonizes the current process. """
    if os.fork() != 0:
        os._exit(0)
    os.setsid()
    if os.fork() != 0:
        os._exit(0)
    os.umask(0o027)
    os.chdir('/')

    os.closerange(0, 3)
    null_fd = os.open(os.devnull, os.O_RDWR)
    if null_fd != 0:
        os.dup2(null_fd, 0)
    os.dup2(null_fd, 1)
    os.dup2(null_fd, 2)

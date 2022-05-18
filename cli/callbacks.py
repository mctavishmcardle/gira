import collections
import functools
import typing

import click

# The input parameter value
V = typing.TypeVar("V")
# The output parameter value
O = typing.TypeVar("O")
GenericClickCallback = collections.abc.Callable[[click.Context, click.Parameter, V], O]


def plain_callback(callback: collections.abc.Callable[[V], O]) -> GenericClickCallback:
    """Wrap a function so it has the correct signature for a `click` callback

    If the input callable doesn't need access to the ocntext or the parameter,
    this is more straightforward & flexible than defining a function that takes
    all of the inputs & ignores all but the parameter value.

    Args:
        callback: The function to wrap
    """
    return functools.wraps(callback)(lambda context, parameter, value: callback(value))


def mapped_callback(
    callback: GenericClickCallback,
    condition: collections.abc.Callable[[V], bool] = lambda value: True,
) -> collections.abc.Callable[[click.Context, click.Parameter, list[V]], list[O]]:
    """Maps a single-value `click` callback to multiple values

    Args:
        callback: The callback to wrap
        condition: An optional test to apply to the input value list, to exclude
            elements whose return-value is falsy
    """
    return functools.wraps(callback)(
        lambda context, parameter, values: [
            callback(context, parameter, value) for value in values if condition(value)
        ]
    )

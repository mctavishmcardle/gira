import collections
import functools
import typing

import click

# The input parameter value
V = typing.TypeVar("V")
# The output parameter value
O = typing.TypeVar("O")

GenericClickCallback = collections.abc.Callable[[click.Context, click.Parameter, V], O]


def none_passthrough(
    callback: collections.abc.Callable[[V], O]
) -> collections.abc.Callable[[typing.Optional[V]], typing.Optional[O]]:
    """Wrap a function to return the input value if it's `None`"""
    return functools.wraps(callback)(
        lambda value: callback(value) if value is not None else None
    )


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


def _compose_callbacks(inner: GenericClickCallback, outer: GenericClickCallback):
    """Pipe the output of an inner callback into the `value` parameter of an outer

    Handles passing the context & parameter arguments to each callback in turn
    """

    @functools.wraps(outer)
    def new_outer(context: click.Context, parameter: click.Parameter, value: V) -> O:
        return outer(context, parameter, inner(context, parameter, value))

    return new_outer


def compose_callbacks(callbacks: list[GenericClickCallback]) -> GenericClickCallback:
    """Pipe a series of callbacks into eachother, sequentially

    Handles passing the context & parameter arguments to each callback in turn
    """
    return functools.wraps(callbacks[0])(
        functools.reduce(
            _compose_callbacks,
            reversed(callbacks),
        )
    )

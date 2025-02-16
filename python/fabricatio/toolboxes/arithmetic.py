"""Arithmetic tools for Fabricatio."""

from fabricatio.models.tool import ToolBox

arithmetic_toolbox = ToolBox(name="ArithmeticToolBox", description="A toolbox for arithmetic operations.")


@arithmetic_toolbox.collect_tool
def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a (float): The first number.
        b (float): The second number.

    Returns:
        float: The sum of the two numbers.
    """
    return a + b


@arithmetic_toolbox.collect_tool
def subtract(a: float, b: float) -> float:
    """Subtract two numbers.

    Args:
        a (float): The first number.
        b (float): The second number.

    Returns:
        float: The result of subtracting b from a.
    """
    return a - b


@arithmetic_toolbox.collect_tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Args:
        a (float): The first number.
        b (float): The second number.

    Returns:
        float: The product of the two numbers.
    """
    return a * b


@arithmetic_toolbox.collect_tool
def divide(a: float, b: float) -> float:
    """Divide two numbers.

    Args:
        a (float): The numerator.
        b (float): The denominator (must not be zero).

    Returns:
        float: The result of dividing a by b.

    """
    return a / b

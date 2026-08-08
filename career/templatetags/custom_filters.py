from django import template

register = template.Library()

@register.filter
def percent_format(value):
    """
    Multiplies the float by 100 and formats as integer percentage.
    """
    try:
        val = float(value)
        return f"{val * 100:.0f}%"
    except (ValueError, TypeError):
        return "0%"

@register.filter
def multiplier(value, arg):
    """
    Multiplies the value by the argument.
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0.0

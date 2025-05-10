from django import template
from django.template.defaultfilters import floatformat
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.safestring import mark_safe
import json
import logging

logger = logging.getLogger(__name__)

register = template.Library()

@register.filter
def money(value, currency=None):
    """Format a value as currency with proper symbol.
    
    Examples:
    {{ value|money:'USD' }} -> $1,234.56
    {{ value|money:'UZS' }} -> 1,234.56 UZS
    """
    if value is None:
        return "—"
        
    formatted = floatformat(value, 2)
    formatted = intcomma(formatted)
    
    if currency == 'USD':
        return f"${formatted}"
    elif currency == 'UZS':
        return f"{formatted} UZS"
    else:
        return formatted

@register.filter
def json_encode(value):
    """
    Safely encode a value as JSON for embedding in a JavaScript context.
    
    Example:
    {{ my_data|json_encode }}
    """
    try:
        return mark_safe(json.dumps(value))
    except Exception as e:
        logger.error(f"JSON encoding error: {str(e)}, value type: {type(value)}")
        # Return empty dict as fallback
        return mark_safe("{}")

@register.filter
def to_list(value):
    """
    Convert a QuerySet or any iterable to a list.
    
    Useful when dealing with QuerySets in templates.
    """
    return list(value)

@register.filter
def add_class(field, css_classes):
    """
    Add CSS classes to a form field.
    
    Example:
    {{ form.username|add_class:"form-control" }}
    """
    return field.as_widget(attrs={"class": css_classes})

@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Returns the URL-encoded query string for the current page,
    updating the given query string parameters.

    Example usage in template:
    <a href="?{% query_transform page=object_list.next_page_number %}">Next</a>
    <a href="?{% query_transform page=1 %}">First</a>
    """
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        query[k] = v
    return query.urlencode()

@register.filter
def startswith(value, arg):
    """
    Check if a string starts with the given argument.
    
    Example:
    {% if payment_method.method_type|startswith:'cash' %}
    """
    if value:
        return str(value).startswith(str(arg))
    return False

@register.filter
def get_by_id(queryset, id_value):
    """
    Get an object from a queryset by its ID.
    
    Example:
    {% with obj=objects|get_by_id:some_id %}
    """
    if not queryset:
        return None
    
    try:
        for obj in queryset:
            if str(obj.id) == str(id_value):
                return obj
    except (AttributeError, ValueError):
        pass
    
    return None 
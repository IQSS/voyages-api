"""Writable filter values shared by request serializers."""
from drf_spectacular.utils import extend_schema_field
from rest_framework.fields import Field


@extend_schema_field({
    "anyOf": [
        {"type": "string"},
        {"type": "integer"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "array", "items": {}},
        {"type": "object"},
    ]
})
class FilterValueField(Field):
    def to_representation(self, value):
        return value

    def to_internal_value(self, data):
        return data

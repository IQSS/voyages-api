from rest_framework import serializers
from rest_framework.fields import SerializerMethodField,IntegerField,CharField
import re
from .models import *
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field


class CRUDLocationTypeSerializer(serializers.ModelSerializer):
	class Meta:
		model=LocationType
		fields='__all__'

class CRUDPolygonSerializer(serializers.ModelSerializer):
	class Meta:
		model=Polygon
		fields='__all__'

class CRUDLocationSerializer(serializers.ModelSerializer):
	spatial_extent=CRUDPolygonSerializer(many=False,allow_null=True)
	location_type=CRUDLocationTypeSerializer(many=False)
	latitude=serializers.FloatField(allow_null=True)
	longitude=serializers.FloatField(allow_null=True)
	class Meta:
		model=Location
		fields='__all__'

class GeoTreeFilterRequestSerializer(serializers.Serializer):
	filter=serializers.JSONField(required=False)

class LocationTypeSerializer(serializers.ModelSerializer):
	class Meta:
		model=LocationType
		fields='__all__'

class PolygonSerializer(serializers.ModelSerializer):
	class Meta:
		model=Polygon
		fields='__all__'

class LocationParentSerializer(serializers.ModelSerializer):
	class Meta:
		model=Location
		fields='__all__'

class LocationChildSerializer(serializers.ModelSerializer):
	class Meta:
		model=Location
		fields='__all__'

class LocationSerializerDeep(serializers.ModelSerializer):
	parent=LocationParentSerializer(many=False,allow_null=True,required=False)
	children=LocationChildSerializer(many=True,allow_null=True,required=False)
	spatial_extent=PolygonSerializer(many=False,allow_null=True,required=False)
	location_type=LocationTypeSerializer(many=False,allow_null=True,required=False)
	name=serializers.CharField(required=False,allow_null=True)
	value=serializers.IntegerField(required=False,allow_null=True)
	class Meta:
		model=Location
		fields='__all__'

class LocationSerializer(serializers.ModelSerializer):
	spatial_extent=PolygonSerializer(many=False,allow_null=True,required=False)
	location_type=LocationTypeSerializer(many=False,allow_null=True,required=False)
	latitude=serializers.FloatField(allow_null=True,required=False)
	longitude=serializers.FloatField(allow_null=True,required=False)
	class Meta:
		model=Location
		fields='__all__'
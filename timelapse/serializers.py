from rest_framework import serializers
from rest_framework.fields import SerializerMethodField,IntegerField,CharField,Field
import re
from voyage.models import *
from document.models import Source,Page,SourcePageConnection,SourceVoyageConnection
from geo.models import Location
from past.models import *
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from common.static.Voyage_options import Voyage_options
from voyage.serializers import VoyageFilterItemSerializer

#################################### THE BELOW SERIALIZERS ARE USED FOR API REQUEST & RESPONSE VALIDATION.
class AnyField(Field):
	def to_representation(self, value):
		return value
	def to_internal_value(self, data):
		return data

class VoyageAnimationGetNationsResponseNodeSerializer(serializers.Serializer):
	name=serializers.CharField()
	code=serializers.IntegerField()

class VoyageAnimationGetNationsResponseSerializer(serializers.Serializer):
	serializers.DictField(child=VoyageAnimationGetNationsResponseNodeSerializer())

class VoyageAnimationGetCompiledRoutesResponseNodeSerializer(serializers.Serializer):
	reg=serializers.IntegerField()
	path=serializers.ListField(child=serializers.ListField(child=serializers.FloatField(),min_length=2,max_length=2,allow_null=True),allow_empty=True)
	name=serializers.CharField()

class VoyageAnimationGetCompiledRoutesPortsResponseSerializer(serializers.Serializer):
	src=serializers.DictField(child=VoyageAnimationGetCompiledRoutesResponseNodeSerializer())
	dst=serializers.DictField(child=VoyageAnimationGetCompiledRoutesResponseNodeSerializer())

class VoyageAnimationGetCompiledRoutesResponseSerializer(serializers.Serializer):
	ports=VoyageAnimationGetCompiledRoutesPortsResponseSerializer()
	routes=serializers.DictField()


class VoyageAnimationGetCompiledRoutesRequestSerializer(serializers.Serializer):
	networkName=serializers.ChoiceField(choices=[
		'intra',
		'trans'
	])

########### PAGINATED VOYAGE LISTS 
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Trans-Atlantic timelapse request',
			summary='Trans-Atlantic timelapse request',
			description='Here, we request the timelapse data for Trans-Atlantic voyages with YEARAM btw 1820-22',
			value={
			  "filter": [
					{
						"varName":"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"searchTerm":[1820,1822],
						"op":"btw"
					},
					{
						"varName":"dataset",
						"searchTerm":0,
						"op":"exact"
					}
				]
			},
			request_only=True
		)
    ]
)
class TimeLapaseRequestSerializer(serializers.Serializer):
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)

class TimeLapseResponseItemSerializer(serializers.Serializer):
	voyage_id=serializers.IntegerField()
	src=serializers.IntegerField()
	dst=serializers.IntegerField()
	regsrc=serializers.IntegerField()
	bregsrc=serializers.IntegerField()
	regdst=serializers.IntegerField()
	bregdst=serializers.IntegerField()
	embarked=serializers.IntegerField()
	disembarked=serializers.IntegerField()
	year=serializers.IntegerField()
	month=serializers.IntegerField()
	ship_ton=serializers.IntegerField()
	nat_id=serializers.IntegerField()
	ship_name=serializers.CharField(allow_blank=True)
	
	
	
	

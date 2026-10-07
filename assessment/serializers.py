from rest_framework import serializers
from rest_framework.fields import SerializerMethodField,IntegerField,CharField,Field
import re
from .models import *
from common.static.Estimate_options import Estimate_options
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

class ImportAreaSerializer(serializers.ModelSerializer):
	class Meta:
		model=ImportArea
		fields='__all__'

class DisembarkationRegionSerializer(serializers.ModelSerializer):
	import_area=ImportAreaSerializer(many=False)
	class Meta:
		model=ImportRegion
		fields='__all__'

class ExportAreaSerializer(serializers.ModelSerializer):
	class Meta:
		model=ExportArea
		fields='__all__'

class EmbarkationRegionSerializer(serializers.ModelSerializer):
	export_area=ExportAreaSerializer(many=False)
	class Meta:
		model=ExportRegion
		fields='__all__'

class NationSerializer(serializers.ModelSerializer):
	class Meta:
		model=Nation
		fields='__all__'

class EstimateSerializer(serializers.ModelSerializer):
	nation=NationSerializer(many=False)
	embarkation_region=EmbarkationRegionSerializer(many=False)
	disembarkation_region=DisembarkationRegionSerializer(many=False)
	class Meta:
		model=Estimate
		fields='__all__'

#################################### THE BELOW SERIALIZERS ARE USED FOR API REQUEST VALIDATION. SOME ARE JUST THIN WRAPPERS ON THE ABOVE, LIKE THAT FOR THE PAGINATED VOYAGE LIST ENDPOINT. OTHERS ARE ALMOST ENTIRELY HAND-WRITTEN/HARD-CODED FOR OUR CUSTOMIZED ENDPOINTS LIKE GEOTREEFILTER AND AUTOCOMPLETE, AND WILL HAVE TO BE KEPT IN ALIGNMENT WITH THE MODELS, VIEWS, AND CUSTOM FUNCTIONS THEY INTERACT WITH.


class AnyField(Field):
	def to_representation(self, value):
		return value
	def to_internal_value(self, data):
		return data

############ REQUEST FIILTER OBJECTS
class EstimateFilterItemSerializer(serializers.Serializer):
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[k for k in Estimate_options])
	searchTerm=AnyField()


############ DATAFRAMES ENDPOINT
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered request for 3 columns',
			summary="Filtered req for 3 cols",
			description="Here, we are looking the continent on which voyages embarked people, in which year, and how many people were disembarked from those voyages.",
			value={
				"selected_fields":[
					'embarkation_region__export_area__name',
					'embarked_slaves',
					'disembarked_slaves'
				],
				"filter":[
					{
						"varName":"year",
						"op":"btw",
						"searchTerm":[1750,1775]
					}
				]
			},
			request_only=True,
			response_only=False
		),
		OpenApiExample(
			'Multi-level, split value columns',
			summary='Multi-level, split value columns',
			description='Here, we request cross-tabs on the geographic locations where enslaved people were embarked, and where they were disembarked. We also request that our columns be grouped in a multi-level way, from broad region to region and place. The cell value we wish to calculate is the number of people embarked and disembarked, and we aggregate these as a sum. We are requesting the first 5 rows of these cross-tab results.',
			value={
				"cols": [
					"embarkation_region__export_area__name",
					"embarkation_region__name"
				],
				"rows": [
					"disembarkation_region__import_area__name",
					"disembarkation_region__name"
				],
				"binsize": None,
				"agg_fn": "sum",
				"vals": ["embarked_slaves"],
				"mode": "html",
				"filter": []
			},
			request_only=True,
			response_only=False
		)
	]
)
class EstimateDataframesRequestSerializer(serializers.Serializer):
	selected_fields=serializers.ListField(
		child=serializers.ChoiceField(choices=[
			k for k in Estimate_options
		])
	)
	filter=EstimateFilterItemSerializer(many=True,allow_null=True,required=False)

############ TIMELINE SERIALIZERS

@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered for histogram w 2 series',
			summary='Filtered 2-series histogram',
			description='Here we request a histogram for numbers of people embarked and disembarked between 1775 and 1820',
			value={
				"filter": [
					{
						"varName":"year",
						"op":"btw",
						"searchTerm":[1775,1820]
					}
				]
			}
		)
	]
)
class EstimateTimelineRequestSerializer(serializers.Serializer):
	filter=EstimateFilterItemSerializer(many=True,allow_null=True,required=False)
	
# class EstimateTimelineResponseSerializer(serializers.Serializer):
# 	disembarked_slaves=serializers.ListField(
# 		child=serializers.IntegerField()
# 	)
# 	embarked_slaves=serializers.ListField(
# 		child=serializers.IntegerField()
# 	)
# 	year=serializers.ListField(
# 		child=serializers.IntegerField()
# 	)

class EstimateTimeLineResponseItemSerializer(serializers.Serializer):
	x=serializers.IntegerField()
	y0=serializers.IntegerField()
	y1=serializers.IntegerField()

############ CROSSTAB SERIALIZERS

@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Request for binned years & embarkation geo vars',
			summary='Multi-level, 20-year bins',
			description='Here, we request cross-tabs on the geographic locations where enslaved people were embarked in 20-year periods. We also request that our columns be grouped in a multi-level way, from broad region to region and place. The cell value we wish to calculate is the number of people embarked, and we aggregate these as a sum.',
			value={
				"cols": [
					"embarkation_region__export_area__name",
					"embarkation_region__name"
				],
				"rows": ["year"],
				"binsize": 20,
				"agg_fn": "sum",
				"vals": ["embarked_slaves","disembarked_slaves"],
				"mode": "html",
				"filter": []
			}
		)
	]
)
class EstimateCrossTabRequestSerializer(serializers.Serializer):
	cols=serializers.ListField(child=serializers.CharField())
	rows=serializers.ListField(child=serializers.CharField())
	binsize=serializers.IntegerField(allow_null=True,required=False)
	vals=serializers.ListField(child=serializers.CharField())
	mode=serializers.ChoiceField(choices=["html","csv"])
	filter=EstimateFilterItemSerializer(many=True,allow_null=True,required=False)
	
class EstimateCrossTabResponseSerializer(serializers.Serializer):
	data=serializers.CharField()







############ VOYAGE AGGREGATION ROUTE MAPS
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'filtered request for voyages to barbados',
			summary="Filtered region-level voyage map req",
			description="Here, using geographic region names, we request voyages that embarked people in 'Sierra Leone' and the 'Gold Coast', and disembarked them in 'Barbados'. We accordingly specify the region zoom level.",
			value={
				"zoomlevel":"region",
				"filter":[
					{
						"varName":"year",
						"op":"btw",
						"searchTerm":[1775,1820]
					}
				]
			}
		)
	]

)
class EstimateAggRoutesRequestSerializer(serializers.Serializer):
	zoomlevel=serializers.ChoiceField(choices=(('broad_region','broad_region'),('region','region')))
	filter=EstimateFilterItemSerializer(many=True,allow_null=True,required=False)

class EstimateAggRoutesEdgesSerializer(serializers.Serializer):
	source=serializers.CharField()
	target=serializers.CharField()
	type=serializers.CharField()
	weight=serializers.IntegerField()
	controls=serializers.ListField(child=serializers.ListField(child=serializers.FloatField(allow_null=False)))

class EstimateAggRoutesNodesDataSerializer(serializers.Serializer):
	lat=serializers.FloatField(allow_null=False)
	lon=serializers.FloatField(allow_null=False)
	name=serializers.CharField(allow_null=True)
	tags=serializers.ListField(child=serializers.CharField(),allow_null=True,required=False)

class EstimateAggRoutesNodesWeightsSerializer(serializers.Serializer):
	disembarkation=serializers.IntegerField()
	embarkation=serializers.IntegerField()
	origin=serializers.IntegerField()
	post_disembarkation=serializers.IntegerField()

class EstimateAggRoutesNodesSerializer(serializers.Serializer):
	id=serializers.CharField()
	weights=EstimateAggRoutesNodesWeightsSerializer()
	data=EstimateAggRoutesNodesDataSerializer()
	
class EstimateAggRoutesResponseSerializer(serializers.Serializer):
	edges=serializers.ListField(child=EstimateAggRoutesEdgesSerializer())
	nodes=serializers.ListField(child=EstimateAggRoutesNodesSerializer())

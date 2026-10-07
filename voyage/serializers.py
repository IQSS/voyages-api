from rest_framework import serializers
from rest_framework.fields import SerializerMethodField,IntegerField,CharField,Field,ListField
import re
from .models import *
from document.models import Source,Page,ShortRef,SourcePageConnection,SourceVoyageConnection
from geo.models import Location
from past.models import *
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from common.static.Voyage_options import Voyage_options
from common.autocomplete_indices import get_all_model_autocomplete_fields
from voyage.cross_filter_fields import VoyageBasicFilterVarNames

#### GEO

class VoyageLocationSerializer(serializers.ModelSerializer):
	class Meta:
		model=Location
		fields='__all__'

##### VESSEL VARIABLES ##### 

class RigOfVesselSerializer(serializers.ModelSerializer):
	class Meta:
		model=RigOfVessel
		fields='__all__'

class NationalitySerializer(serializers.ModelSerializer):
	class Meta:
		model=Nationality
		fields='__all__'


class TonTypeSerializer(serializers.ModelSerializer):
	class Meta:
		model=TonType
		fields='__all__'

class VoyageShipSerializer(serializers.ModelSerializer):
	rig_of_vessel=RigOfVesselSerializer(many=False,read_only=True)
	imputed_nationality=NationalitySerializer(many=False,read_only=True)
	nationality_ship=NationalitySerializer(many=False,read_only=True)
	ton_type=TonTypeSerializer(many=False,read_only=True)
	vessel_construction_place=VoyageLocationSerializer(many=False,read_only=True)
	vessel_construction_region=VoyageLocationSerializer(many=False,read_only=True)
	registered_place=VoyageLocationSerializer(many=False,read_only=True)
	registered_region=VoyageLocationSerializer(many=False,read_only=True)
	class Meta:
		model=VoyageShip
		fields='__all__'


##### ENSLAVED NUMBERS ##### 



class VoyageSlavesNumbersSerializer(serializers.ModelSerializer):
	class Meta:
		model=VoyageSlavesNumbers
		fields='__all__'




##### SPECIAL VARS ##### 

class AfricanInfoSerializer(serializers.ModelSerializer):
	class Meta:
		model=AfricanInfo
		fields='__all__'

class CargoTypeSerializer(serializers.ModelSerializer):
	class Meta:
		model=CargoType
		fields='__all__'

##### CREW NUMBERS ##### 

class VoyageCrewSerializer(serializers.ModelSerializer):
	class Meta:
		model=VoyageCrew
		fields='__all__'



##### ITINERARY #####

class VoyageItinerarySerializer(serializers.ModelSerializer):
	port_of_departure=VoyageLocationSerializer(many=False,read_only=True)
	int_first_port_emb=VoyageLocationSerializer(many=False,read_only=True)
	int_second_port_emb=VoyageLocationSerializer(many=False,read_only=True)
	int_first_region_purchase_slaves=VoyageLocationSerializer(many=False,read_only=True)
	int_second_region_purchase_slaves=VoyageLocationSerializer(many=False,read_only=True)
	int_first_port_dis=VoyageLocationSerializer(many=False,read_only=True)
	int_second_port_dis=VoyageLocationSerializer(many=False,read_only=True)
	int_first_region_slave_landing=VoyageLocationSerializer(many=False,read_only=True)
	imp_principal_region_slave_dis=VoyageLocationSerializer(many=False,read_only=True)
	int_second_place_region_slave_landing=VoyageLocationSerializer(many=False,read_only=True)
	first_place_slave_purchase=VoyageLocationSerializer(many=False,read_only=True)
	second_place_slave_purchase=VoyageLocationSerializer(many=False,read_only=True)
	third_place_slave_purchase=VoyageLocationSerializer(many=False,read_only=True)
	first_region_slave_emb=VoyageLocationSerializer(many=False,read_only=True)
	second_region_slave_emb=VoyageLocationSerializer(many=False,read_only=True)
	third_region_slave_emb=VoyageLocationSerializer(many=False,read_only=True)
	port_of_call_before_atl_crossing=VoyageLocationSerializer(many=False,read_only=True)
	first_landing_place=VoyageLocationSerializer(many=False,read_only=True)
	second_landing_place=VoyageLocationSerializer(many=False,read_only=True)
	third_landing_place=VoyageLocationSerializer(many=False,read_only=True)
	first_landing_region=VoyageLocationSerializer(many=False,read_only=True)
	second_landing_region=VoyageLocationSerializer(many=False,read_only=True)
	third_landing_region=VoyageLocationSerializer(many=False,read_only=True)
	place_voyage_ended=VoyageLocationSerializer(many=False,read_only=True)
	region_of_return=VoyageLocationSerializer(many=False,read_only=True)
	broad_region_of_return=VoyageLocationSerializer(many=False,read_only=True)
	imp_port_voyage_begin=VoyageLocationSerializer(many=False,read_only=True)
	imp_region_voyage_begin=VoyageLocationSerializer(many=False,read_only=True)
	imp_broad_region_voyage_begin=VoyageLocationSerializer(many=False,read_only=True)
	principal_place_of_slave_purchase=VoyageLocationSerializer(many=False,read_only=True)
	imp_principal_place_of_slave_purchase=VoyageLocationSerializer(many=False,read_only=True)
	imp_principal_region_of_slave_purchase=VoyageLocationSerializer(many=False,read_only=True)
	imp_broad_region_of_slave_purchase=VoyageLocationSerializer(many=False,read_only=True)
	principal_port_of_slave_dis=VoyageLocationSerializer(many=False,read_only=True)
	imp_principal_port_slave_dis=VoyageLocationSerializer(many=False,read_only=True)
	imp_broad_region_slave_dis=VoyageLocationSerializer(many=False,read_only=True)
	int_fourth_port_dis=VoyageLocationSerializer(many=False,read_only=True)
	int_third_port_dis=VoyageLocationSerializer(many=False,read_only=True)
	int_fourth_port_dis=VoyageLocationSerializer(many=False,read_only=True)
	int_third_place_region_slave_landing=VoyageLocationSerializer(many=False,read_only=True)
	int_fourth_place_region_slave_landing=VoyageLocationSerializer(many=False,read_only=True)
	class Meta:
		model=VoyageItinerary
		fields='__all__'

##### OUTCOMES #####

class ParticularOutcomeSerializer(serializers.ModelSerializer):
	class Meta:
		model=ParticularOutcome
		fields='__all__'

class SlavesOutcomeSerializer(serializers.ModelSerializer):
	class Meta:
		model=SlavesOutcome
		fields='__all__'
		
class ResistanceSerializer(serializers.ModelSerializer):
	class Meta:
		model=Resistance
		fields='__all__'

class OwnerOutcomeSerializer(serializers.ModelSerializer):
	class Meta:
		model=OwnerOutcome
		fields='__all__'

class VesselCapturedOutcomeSerializer(serializers.ModelSerializer):
	class Meta:
		model=VesselCapturedOutcome
		fields='__all__'
		
class VoyageOutcomeSerializer(serializers.ModelSerializer):
	outcome_owner=OwnerOutcomeSerializer(many=False,read_only=True)
	outcome_slaves=SlavesOutcomeSerializer(many=False,read_only=True)
	particular_outcome=ParticularOutcomeSerializer(many=False,read_only=True)
	resistance=ResistanceSerializer(many=False,read_only=True)
	vessel_captured_outcome=VesselCapturedOutcomeSerializer(many=False,read_only=True)
	class Meta:
		model=VoyageOutcome
		fields='__all__'


#### DATES #####
class VoyageSparseDateSerializer(serializers.ModelSerializer):
	date_str=serializers.SerializerMethodField()
	class Meta:
		model=VoyageSparseDate
		fields=['date_str','year']
	def get_date_str(self,instance) -> CharField():
		date=instance
		if date:
			date_str=date.__str__()
		else:
			date_str=None
		return date_str
		
class VoyageDatesSerializer(serializers.ModelSerializer):
	voyage_began_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	slave_purchase_began_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	date_departed_africa_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	imp_arrival_at_port_of_dis_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	departure_last_place_of_landing_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	voyage_completed_sparsedate_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	
	vessel_left_port_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	first_dis_of_slaves_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	arrival_at_second_place_landing_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	third_dis_of_slaves_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	voyage_completed_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	imp_voyage_began_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	imp_departed_africa_sparsedate=VoyageSparseDateSerializer(many=False,read_only=True)
	class Meta:
		model=VoyageDates
		fields='__all__'
	
class VoyageSourceShortRefSerializer(serializers.ModelSerializer):
	class Meta:
		model=ShortRef
		fields=['id','name']


class VoyageSourceSerializer(serializers.ModelSerializer):
	short_ref=VoyageSourceShortRefSerializer(many=False)
	bib=serializers.SerializerMethodField()
	class Meta:
		model=Source
		fields=['short_ref','title','bib','has_published_manifest','zotero_group_id','zotero_item_id']
	def get_bib(self,instance) -> CharField():
		raw_bib=instance.bib
		#strip out paragraph tags injected by zotero
		if raw_bib is not None:
			raw_bib=re.sub("</*p.*?>","",raw_bib)
			raw_bib=re.sub("</*div.*?>","",raw_bib)
			raw_bib=re.sub("\\n"," ",raw_bib)
		text_refs=[t for t in instance.page_ranges if t is not None]
		if len(text_refs)>0:
			return f"{raw_bib}: {', '.join(text_refs)}"
		else:
			return raw_bib

class VoyageEnslavedSerializer(serializers.ModelSerializer):
	class Meta:
		model=Enslaved
		fields=['id','enslaved_id','documented_name']

class VoyageGroupingsSerializer(serializers.ModelSerializer):
	class Meta:
		model=VoyageGroupings
		fields='__all__'

class AfricanInfoSerializer(serializers.ModelSerializer):
	class Meta:
		model=AfricanInfo
		fields='__all__'


class CargoTypeSerializer(serializers.ModelSerializer):
	class Meta:
		model=CargoType
		fields='__all__'

class CargoUnitSerializer(serializers.ModelSerializer):
	class Meta:
		model=CargoUnit
		fields='__all__'

class VoyageCargoConnectionSerializer(serializers.ModelSerializer):
	cargo=CargoTypeSerializer(many=False,read_only=True)
	unit=CargoUnitSerializer(many=False,read_only=True)
	amount=serializers.FloatField(read_only=True)
	class Meta:
		model=VoyageCargoConnection
		fields='__all__'

class VoyageEnslaverSerializer(serializers.Serializer):
	id=serializers.IntegerField()
	name_and_role=serializers.CharField()


class LinkedVoyageSerializer(serializers.Serializer):
	voyage_id=serializers.IntegerField()

class VoyageSerializer(serializers.ModelSerializer):
	sources=serializers.SerializerMethodField()
	voyage_itinerary=VoyageItinerarySerializer(many=False,read_only=True)
	voyage_dates=VoyageDatesSerializer(many=False,read_only=True)
	enslavers=serializers.SerializerMethodField()
	named_enslaved_people=serializers.SerializerMethodField()
	voyage_crew=VoyageCrewSerializer(many=False,read_only=True)
	voyage_ship=VoyageShipSerializer(many=False,read_only=True)
	voyage_slaves_numbers=VoyageSlavesNumbersSerializer(many=False,read_only=True)
	voyage_outcome=VoyageOutcomeSerializer(many=False,read_only=True)
	voyage_groupings=VoyageGroupingsSerializer(many=False,read_only=True)
	cargo=serializers.SerializerMethodField()
	african_info=AfricanInfoSerializer(many=True,read_only=True)
	linked_voyages=serializers.SerializerMethodField()
	
	def get_cargo(self,instance) -> ListField(child=serializers.CharField()):
		cargoconnections=instance.cargo.all()
		cargo_return=[]
		for cc in cargoconnections:
			cargo=cc.cargo.name
			unit=cc.unit
			amount=cc.amount
			cargo_return.append(" ".join([i for i in [amount,unit,cargo] if i is not None]))
		return cargo_return
	
	def get_linked_voyages(self,instance) -> VoyageSourceSerializer(many=True):
		incoming=instance.incoming_from_other_voyages.all()
		outgoing=instance.outgoing_to_other_voyages.all()
		incoming_ids=[i.first for i in incoming]
		outgoing_ids=[o.second for o in outgoing]
		linked_voyage_ids=list(set(incoming_ids+outgoing_ids))
		return LinkedVoyageSerializer(linked_voyage_ids,many=True,read_only=True).data

	##DIDN'T DO LINKED VOYAGES YET
	def get_sources(self,instance) -> VoyageSourceSerializer(many=True):
		vscs=instance.voyage_source_connections.all()
		
		sources_dict={}
		
		for vsc in vscs:
			page_range=vsc.page_range
			s=vsc.source
			s_id=s.id
			s.page_ranges=[page_range]
			if s_id not in sources_dict:
				sources_dict[s_id]=s
			else:
				sources_dict[s_id].page_ranges.append(page_range)
		return VoyageSourceSerializer([sources_dict[i] for i in sources_dict],many=True,read_only=True).data

	def get_named_enslaved_people(self,instance) -> VoyageEnslavedSerializer(many=True):
		ers=instance.voyage_enslavement_relations.all()
		enslaved_dict={}
		for er in ers:
			eirs=er.enslaved_in_relation.all()
			for eir in eirs:
				enslaved_person=eir.enslaved
				enslaved_dict[enslaved_person.id]=enslaved_person
		return VoyageEnslavedSerializer([enslaved_dict[i] for i in enslaved_dict],many=True,read_only=True).data
	def get_enslavers(self,instance) -> ListField(child=serializers.CharField()):
		ers=instance.voyage_enslavement_relations.all()
		ers=ers.prefetch_related('relation_enslavers__roles','relation_enslavers__enslaver_alias__identity')
		enslaver_roles_and_identity_pks=ers.values_list('relation_enslavers__roles__id','relation_enslavers__enslaver_alias__identity_id')
		enslavers_and_roles={}
		for eraipk in enslaver_roles_and_identity_pks:
			rolepk,enslaverpk=eraipk
			if rolepk is not None and enslaverpk is not None:
				if enslaverpk not in enslavers_and_roles:
					enslavers_and_roles[enslaverpk]=[rolepk]
				else:
					enslavers_and_roles[enslaverpk].append(rolepk)
		enslavers_and_roles_list=[
			{'roles':', '.join(
				[EnslaverRole.objects.get(id=rolepk).name for rolepk in enslavers_and_roles[enslaverpk]]
				),
				'enslaver':EnslaverIdentity.objects.get(id=enslaverpk)
			} for enslaverpk in enslavers_and_roles
		]
		enslavers_in_relation=[]
		for er in enslavers_and_roles_list:
			roles=er['roles']
			enslaver=er['enslaver']
			if roles is not None:
				name_and_role=f"{enslaver.principal_alias} ({roles})"
			else:
				name_and_role=enslaver
			enslaver_dict={"id":enslaver.id,"name_and_role":name_and_role}
			enslavers_in_relation.append(enslaver_dict)	
		return VoyageEnslaverSerializer(enslavers_in_relation,many=True,read_only=True).data
	class Meta:
		model=Voyage
		fields='__all__'

#################################### THE BELOW SERIALIZERS ARE USED FOR API REQUEST VALIDATION. SOME ARE JUST THIN WRAPPERS ON THE ABOVE, LIKE THAT FOR THE PAGINATED VOYAGE LIST ENDPOINT. OTHERS ARE ALMOST ENTIRELY HAND-WRITTEN/HARD-CODED FOR OUR CUSTOMIZED ENDPOINTS LIKE GEOTREEFILTER AND AUTOCOMPLETE, AND WILL HAVE TO BE KEPT IN ALIGNMENT WITH THE MODELS, VIEWS, AND CUSTOM FUNCTIONS THEY INTERACT WITH.
class AnyField(Field):
	def to_representation(self, value):
		return value
	def to_internal_value(self, data):
		return data

############ REQUEST FIILTER OBJECTS
class VoyageBasicFilterItemSerializer(serializers.Serializer):
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	##It's rather costly for our filter requests like autocomplete and geotree to themselves "cross-filter" on too many nested variables
	##At the same time, some cross-filters are essential to build the menus properly
	varName=serializers.ChoiceField(choices=VoyageBasicFilterVarNames)
	searchTerm=AnyField()


class VoyageFilterItemSerializer(serializers.Serializer):
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[
		k for k in Voyage_options
	]+["EnslaverNameAndRole"])
	searchTerm=AnyField()

########### PAGINATED VOYAGE LISTS 
@extend_schema_serializer(
	examples = [
		 OpenApiExample(
			'Paginated request for filtered voyages.',
			summary='Paginated request for filtered voyages.',
			description='Here, we request page 2 (with 5 items per page) of voyages for which enslaved people were purchased in Cuba or Florida between 1820-1822.',
			value={
			  "filter": [
					{
						"varName":"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"searchTerm":1820,
						"op":"gte"
					},
					{
						"varName":"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"searchTerm":1822,
						"op":"lte"
					},
					{
						"varName":"voyage_itinerary__imp_principal_region_of_slave_purchase__name",
						"searchTerm":[
							"Florida",
							"Cuba"
						],
						"op":"in"
					}
				],
				"page": 2,
				"page_size": 5
			},
			request_only=True
		)
	]
)
class VoyageListRequestSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False,allow_null=True)
	page_size=serializers.IntegerField(required=False,allow_null=True)
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	order_by=serializers.ListField(child=serializers.CharField(),allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)

class VoyageListResponseSerializer(serializers.Serializer):
	page=serializers.IntegerField()
	page_size=serializers.IntegerField()
	count=serializers.IntegerField()
	results=VoyageSerializer(many=True,read_only=True)


############ LINE, BAR, AND PIE CHARTS
### I would like to roll these together, but pie charts can only accept one value field, whereas line and bar charts can accept one or more

yearbinoptions=[f'voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year__bins__{n}'
	for n in [5,10,25]
]

class VoyagePieChartParamsRequestSerializer(serializers.Serializer):
	by=serializers.ChoiceField(choices=[
		k for k in Voyage_options if Voyage_options[k]['type'] in [
			'string'
		]
	] + yearbinoptions)
	vals=serializers.ChoiceField(choices=[
		k for k in Voyage_options if Voyage_options[k]['type'] in [
			'integer',
			'number'
		]
	])
	agg_fn=serializers.ChoiceField(choices=["mean","sum","max","min","count"])
	
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered Pie Chart Request',
			summary="Filtered Pie Chart Request",
			description="Here, we are requesting a long df of the number of people who were embarked in different regions on voyages that landed in Barbados.",
			value={
				"groupby":{
					"by": "voyage_itinerary__imp_principal_region_of_slave_purchase__name",
					"vals":"voyage_slaves_numbers__imp_total_num_slaves_embarked",
					"agg_fn":"sum"
				},
				"filter":[
					{
						"varName": "voyage_itinerary__imp_principal_region_slave_dis__name",
						"op": "in",
						"searchTerm": ["Barbados"]
					}
				]
			}
		),
		OpenApiExample(
			'Filtered Pie Chart Request with Year Bins/Intervals',
			summary="Filtered Pie Chart Request with Year Bins/Intervals",
			description="Here, we are requesting a long df of how many people were embarked in 20-year periods on voyages that landed in Barbados.",
			value={
				"groupby": {
					"by": "voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year__bins__25",
					"vals": "voyage_slaves_numbers__imp_total_num_slaves_embarked",
					"agg_fn": "sum"
				},
				"filter": [
					{
						"varName": "voyage_itinerary__imp_principal_region_slave_dis__name",
						"op": "in",
						"searchTerm": [
							"Barbados"
						]
					}
				]
			}
		)
	]
)
class VoyagePieChartRequestSerializer(serializers.Serializer):
	groupby=VoyagePieChartParamsRequestSerializer(many=False,allow_null=False,required=True)
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)


class VoyageAggSeriesSerializer(serializers.Serializer):
	vals=serializers.ChoiceField(choices=[
			k for k in Voyage_options if Voyage_options[k]['type'] in [
				'integer',
				'number'
			]
		]
	)
	agg_fn=serializers.ChoiceField(choices=["mean","sum","max","min","count"])

class VoyageLineAndBarChartParamsRequestSerializer(serializers.Serializer):
	by=serializers.ChoiceField(choices=[k for k in Voyage_options] + yearbinoptions)
	agg_series=VoyageAggSeriesSerializer(many=True)

############ BAR AND LINE CHARTS
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered Pie Chart Request',
			summary="Filtered scatter plot req",
			description="Here, we consider voyages that landed in Barbados, and request a long dataframe showing how many people in total embarked from each region.",
			value={
				"groupby":{
					"by": "voyage_itinerary__imp_principal_region_of_slave_purchase__name",
					"agg_series":[
						{
							"vals":"voyage_slaves_numbers__imp_total_num_slaves_embarked",
							"agg_fn":"sum"
						}
					]
				},
				"filter":[
					{
						"varName": "voyage_itinerary__imp_principal_region_slave_dis__name",
						"op": "in",
						"searchTerm": ["Barbados"]
					}
				]
			}
		)
	]
)
class VoyageLineAndBarChartsRequestSerializer(serializers.Serializer):
	groupby=VoyageLineAndBarChartParamsRequestSerializer(many=False,allow_null=False,required=True)
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)

############ DATAFRAMES ENDPOINT
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered request for 3 columns',
			summary="Filtered req for 3 cols",
			description="Here, we are looking for the ship name, the year of disembarkation, and the name(s) of the associated enslaver(s) for voyages that disembarked captives in the years 1810-15.",
			value={
				"selected_fields":[
					"voyage_id",
					"voyage_ship__ship_name",
					"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year"
				],
				"filter":[
					{
						"varName": "voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"op": "btw",
						"searchTerm": [1810,1815]
					}
				]
			}
		)
	]
)
class VoyageDataframesRequestSerializer(serializers.Serializer):
	selected_fields=serializers.ListField(
		child=serializers.ChoiceField(choices=[
			k for k in Voyage_options
		])
	)
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)

############ VOYAGE GEOTREE REQUESTS
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'filtered request for voyages',
			summary="Filtered geo tree request",
			description="Here, we are looking for a tree of all the values used for the port of departure variable on Transatlantic voyages that disembarked enslaved people in Baltimore",
			value={
				"geotree_valuefields":["voyage_itinerary__port_of_departure__value"],
				"filter":[
					{
						"varName": "voyage_itinerary__imp_principal_port_slave_dis__name",
						"op": "in",
						"searchTerm": ["Baltimore"]
					},
					{
						"varName": "dataset",
						"op": "exact",
						"searchTerm": 0
					}
				]
			}
		)
	]
)
class VoyageGeoTreeFilterRequestSerializer(serializers.Serializer):
	geotree_valuefields=serializers.ListField(
		child=serializers.ChoiceField(
			choices=[
				k for k in Voyage_options
				if (re.match("^voyage_itinerary[a-z|_]+",k) or re.match("^voyage_ship[a-z|_]+[region|place][a-z|_]+",k))
				and k.endswith("value")
			]
		)
	)
	filter=VoyageBasicFilterItemSerializer(many=True,allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)

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
						"varName":"voyage_itinerary__imp_principal_region_slave_dis__name",
						"searchTerm":["Barbados"],
						"op":"in"
					},
					{
						"varName":"voyage_itinerary__imp_principal_region_of_slave_purchase__name",
						"searchTerm":["Sierra Leone","Gold Coast"],
						"op":"in"
					}
				]
			}
		)
	]

)
class VoyageAggRoutesRequestSerializer(serializers.Serializer):
	zoomlevel=serializers.ChoiceField(choices=(('region','region'),('place','place')))
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)

class VoyageAggRoutesEdgesSerializer(serializers.Serializer):
	source=serializers.CharField()
	target=serializers.CharField()
	type=serializers.CharField()
	weight=serializers.IntegerField()
	controls=serializers.ListField(child=serializers.ListField(child=serializers.FloatField(allow_null=False)))

class VoyageAggRoutesNodesDataSerializer(serializers.Serializer):
	lat=serializers.FloatField(allow_null=False)
	lon=serializers.FloatField(allow_null=False)
	name=serializers.CharField(allow_null=True)
	tags=serializers.ListField(child=serializers.CharField(),allow_null=True,required=False)

class VoyageAggRoutesNodesWeightsSerializer(serializers.Serializer):
	disembarkation=serializers.IntegerField()
	embarkation=serializers.IntegerField()
	origin=serializers.IntegerField()
	post_disembarkation=serializers.IntegerField()

class VoyageAggRoutesNodesSerializer(serializers.Serializer):
	id=serializers.CharField()
	weights=VoyageAggRoutesNodesWeightsSerializer()
	data=VoyageAggRoutesNodesDataSerializer()
	
class VoyageAggRoutesResponseSerializer(serializers.Serializer):
	edges=serializers.ListField(child=VoyageAggRoutesEdgesSerializer())
	nodes=serializers.ListField(child=VoyageAggRoutesNodesSerializer())

############ AGGREGATION FIELD
@extend_schema_serializer(
	examples = [
		 OpenApiExample(
			'Filtered request for min/max',
			summary='Filtered request for min/max',
			description='Here, we request the min and max number of people who were embarked on individual voyages before the year 1620.',
			value={
				"varName": "voyage_slaves_numbers__imp_total_num_slaves_embarked",
				"filter": [
					{
						"varName":"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"op":"lte",
						"searchTerm":1620
					}
				]
			},
			request_only=True
		)
	]
)
class VoyageFieldAggregationRequestSerializer(serializers.Serializer):
	varName=serializers.ChoiceField(choices=[
		k for k in Voyage_options if Voyage_options[k]['type'] in [
			'integer',
			'number'
		]
	])
	
class VoyageFieldAggregationResponseSerializer(serializers.Serializer):
	varName=serializers.ChoiceField(choices=[
		k for k in Voyage_options if Voyage_options[k]['type'] in [
			'integer',
			'number'
		]
	])
	min=serializers.IntegerField(allow_null=True)
	max=serializers.IntegerField(allow_null=True)


############ OFFSET PAGINATION SERIALIZERS
class VoyageOffsetPaginationSerializer(serializers.Serializer):
	offset=serializers.IntegerField()
	limit=serializers.IntegerField()
	total_results_count=serializers.IntegerField()

############ CROSSTAB SERIALIZERS
@extend_schema_serializer(
	examples=[	
		OpenApiExample(
			'Paginated request for binned years & embarkation geo vars',
			summary='Multi-level, paginated, 20-year bins',
			description='Here, we request cross-tabs on the geographic locations where enslaved people were embarked in 20-year periods. We also request that our columns be grouped in a multi-level way, from broad region to region and place. The cell value we wish to calculate is the number of people embarked, and we aggregate these as a sum. We are requesting the first 5 rows of these cross-tab results.',
			value={
				"columns":[
					"voyage_itinerary__imp_broad_region_of_slave_purchase__name",
					"voyage_itinerary__imp_principal_region_of_slave_purchase__name",
					"voyage_itinerary__imp_principal_place_of_slave_purchase__name"
				],
				"rows":"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
				"binsize": 20,
				"rows_label":"YEARAM",
				"agg_fn":"sum",
				"value_field":"voyage_slaves_numbers__imp_total_num_slaves_embarked",
				"offset":0,
				"limit":5,
				"filter":[]
			},
			request_only=True,
			response_only=False
		),
		OpenApiExample(
			'Paginated request for binned years & embarkation geo vars',
			summary='Multi-level, paginated, 20-year bins',
			description='Here, we request cross-tabs on the geographic locations where enslaved people were embarked in 20-year periods. We also request that our columns be grouped in a multi-level way, from broad region to region and place. The cell value we wish to calculate is the number of people embarked, and we aggregate these as a sum. We are requesting the first 5 rows of these cross-tab results.',
			value={
				"columns":[
					"voyage_itinerary__imp_broad_region_of_slave_purchase__name",
					"voyage_itinerary__imp_principal_region_of_slave_purchase__name",
					"voyage_itinerary__imp_principal_place_of_slave_purchase__name"
				],
				"rows":"voyage_itinerary__imp_principal_region_slave_dis__name",
				"binsize": None,
				"rows_label":"Imputed Principle Port of Disembarkation (MJSLPTIMP)",
				"agg_fn":"sum",
				"value_field":"voyage_slaves_numbers__imp_total_num_slaves_embarked",
				"offset":20,
				"limit":10,
				"filter":[],
				"order_by": ["-Africa__Senegambia and offshore Atlantic__Saint-Louis"]
			},
			request_only=True,
			response_only=False
		)
	]
)
class VoyageCrossTabRequestSerializer(serializers.Serializer):
	columns=serializers.ListField(child=serializers.CharField())
	rows=serializers.CharField()
	binsize=serializers.IntegerField(allow_null=True,required=False)
	rows_label=serializers.CharField(allow_null=True)
	agg_fn=serializers.CharField()
	value_field=serializers.CharField()
	offset=serializers.IntegerField()
	limit=serializers.IntegerField()
	order_by=serializers.ListField(child=serializers.CharField(),allow_null=True,required=False)
	global_search=serializers.CharField(allow_null=True,required=False)
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	
class VoyageCrossTabResponseSerializer(serializers.Serializer):
	tablestructure=serializers.JSONField()
	data=serializers.JSONField()
	metadata=VoyageOffsetPaginationSerializer()

@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Summary Stats',
			summary='Summary Stats',
			description='This is a customized, kind of funky, summary statistics table. Here, we see summary stats for the transatlantic voyages.',
			value={
				"mode": "html",
				"filter": [
					{
						"op": "exact",
						"varName": "dataset",
						"searchTerm": 0
					}
				]
			}
		)
	]
)
class VoyageSummaryStatsRequestSerializer(serializers.Serializer):
	mode=serializers.ChoiceField(choices=["html","csv"])
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)
	
class VoyageSummaryStatsResponseSerializer(serializers.Serializer):
	data=serializers.CharField()


@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Download CSV',
			summary='Download CSV',
			description='Allows users to download the filtered dataset in csv format.',
			value={
				"filter": [
					{
						"op": "exact",
						"varName": "dataset",
						"searchTerm": 0
					}
				]
			}
		)
	]
)
class VoyageDownloadRequestSerializer(serializers.Serializer):
# 	mode=serializers.ChoiceField(choices=["csv","excel"])
	filter=VoyageFilterItemSerializer(many=True,allow_null=True,required=False)

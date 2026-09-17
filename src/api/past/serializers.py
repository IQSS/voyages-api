from rest_framework import serializers
from rest_framework.fields import SerializerMethodField,IntegerField,CharField,Field,ListField
import re
from .models import *
from geo.models import Location
from voyage.models import *
from document.models import Source, ShortRef,SourceEnslavedConnection, SourceEnslaverConnection,SourceVoyageConnection
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample
from common.static.EnslaverIdentity_options import EnslaverIdentity_options
from common.static.Enslaved_options import Enslaved_options
from common.static.EnslavementRelation_options import EnslavementRelation_options
from common.autocomplete_indices import get_all_model_autocomplete_fields
from past.cross_filter_fields import EnslaverBasicFilterVarNames,EnslavedBasicFilterVarNames
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field



	
def pretty_date(month,day,year):
	month_string_dict={
		1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"
	}
	if year is not None:
		if month is not None:
			month=month_string_dict[month]
			if day is not None:
				date=f'{month} {day}, {year}'
			else:
				date=f'{month} {year}'
		else:
			date=f'{year}'
	else:
		date=None
	return date

#################################### THE BELOW SERIALIZERS ARE USED FOR API REQUEST VALIDATION. SOME ARE JUST THIN WRAPPERS ON THE ABOVE, LIKE THAT FOR PAGINATED LISTS. OTHERS ARE ALMOST ENTIRELY HAND-WRITTEN/HARD-CODED FOR OUR CUSTOMIZED ENDPOINTS LIKE GEOTREEFILTER AND AUTOCOMPLETE, AND WILL HAVE TO BE KEPT IN ALIGNMENT WITH THE MODELS, VIEWS, AND CUSTOM FUNCTIONS THEY INTERACT WITH.

class AnyField(Field):
	def to_representation(self, value):
		return value

	def to_internal_value(self, data):
		return data
		
############ CONTROLLED VOCAB SERIALIZERS

class CaptiveFateSerializer(serializers.ModelSerializer):
	class Meta:
		model=CaptiveFate
		fields='__all__'

class GenderSerializer(serializers.ModelSerializer):
	class Meta:
		model=Gender
		fields='__all__'

class EnslaverRoleSerializer(serializers.ModelSerializer):
	class Meta:
		model=EnslaverRole
		fields='__all__'

class PastLocationSerializer(serializers.ModelSerializer):
	class Meta:
		model=Location
		fields='__all__'

class PastSourceShortRefSerializer(serializers.ModelSerializer):
	class Meta:
		model=ShortRef
		fields=['id','name']

class PastSourceSerializer(serializers.ModelSerializer):
	page_ranges=serializers.ListField(child=serializers.CharField(required=False),required=False)
	short_ref=PastSourceShortRefSerializer(many=False,allow_null=True,required=False)
	class Meta:
		model=Source
		fields='__all__'
 
############ VOYAGES


class PastVoyageOutcomesSerializer(serializers.Serializer):
	particular_outcome=serializers.CharField(required=False)
	class Meta:
		fields=['particular_outcome']

class PastEnslavedVoyageSerializer(serializers.Serializer):
	id=serializers.IntegerField(required=False)
	embarkation=serializers.CharField(required=False)
	disembarkation=serializers.CharField(required=False)
	year=serializers.IntegerField(required=False)
	month=serializers.IntegerField(required=False)
	day=serializers.IntegerField(required=False)
	ship_name=serializers.CharField(required=False)
	outcomes=PastVoyageOutcomesSerializer(many=False,required=False,allow_null=True)
	class Meta:
		fields=[
			'id',
			'embarkation',
			'disembarkation',
			'year',
			'month',
			'day',
			'ship_name',
			'outcomes'
		]


#######################

#### ENSLAVED & ONE-TO-ONE RELATIONS

class CaptiveFateSerializer(serializers.ModelSerializer):
	class Meta:
		model=CaptiveFate
		fields='__all__'

class CaptiveStatusSerializer(serializers.ModelSerializer):
	class Meta:
		model=CaptiveStatus
		fields='__all__'

class LanguageGroupSerializer(serializers.ModelSerializer):
	class Meta:
		model=LanguageGroup
		fields='__all__'

class EnslavedEnslaverSerializer(serializers.Serializer):
	id=serializers.IntegerField(required=False)
	name_and_role=serializers.CharField(required=False)

class EnslavedSerializer(serializers.ModelSerializer):
	enslaved_id=serializers.IntegerField(read_only=True)
	post_disembark_location=PastLocationSerializer(many=False,required=False,allow_null=True)
	captive_fate=CaptiveFateSerializer(many=False,required=False,allow_null=True)
	voyages=serializers.SerializerMethodField(required=False,allow_null=True)
	enslavers=serializers.SerializerMethodField(required=False,allow_null=True)
	captive_status=CaptiveStatusSerializer(many=False,required=False,allow_null=True)
	language_group=LanguageGroupSerializer(many=False,required=False,allow_null=True)
	sources=serializers.SerializerMethodField(required=False,allow_null=True)
	gender=serializers.SerializerMethodField(required=False,allow_null=True)
	
	def get_gender(self,instance) -> serializers.CharField():
		gender=instance.gender
		if gender:
			gender=gender.name
		else:
			gender=None
		return gender
	
	def get_sources(self,instance) -> PastSourceSerializer(many=True):
		source_ids=list(set([i[0] for i in Enslaved.objects.all().filter(id=instance.id).values_list('enslaved_relations__relation__voyage__voyage_source_connections__source')]))
		sources=Source.objects.all().filter(id__in=source_ids)
		return PastSourceSerializer(sources,many=True).data

	def get_voyages(self,instance) -> PastEnslavedVoyageSerializer(many=False):
		#right now, the table layouts, basically everything assume a single voyage per enslaved person
		v=Voyage.objects.filter(voyage_enslavement_relations__enslaved_in_relation__enslaved__id=instance.id).first()
		if v is not None:
			embark=v.voyage_itinerary.imp_principal_place_of_slave_purchase
			if embark:
				embark=embark.name
				embark=fuzzyplacenamestrip(embark)
			else:
				embark="place unknown"
			disembark=v.voyage_itinerary.imp_principal_port_slave_dis
			if disembark:
				disembark=disembark.name
				disembark=fuzzyplacenamestrip(disembark)
			else:
				disembark="place unknown"
			date=v.voyage_dates.imp_arrival_at_port_of_dis_sparsedate
			if date:
				yearam=date.year
				month=date.month
				day=date.day
			else:
				yearam="year unknown"
				month=None
				day=None
			try:
				ship=v.voyage_ship
				ship_name=ship.ship_name
			except VoyageShip.DoesNotExist:
				ship_name="ship unknown"
			
			particular_outcome=v.voyage_outcome.particular_outcome
			if not particular_outcome:
				particular_outcome="outcome unknown"
			else:
				particular_outcome=particular_outcome.name
			v_id=v.id
		else:
			v_id=None
			embark=None
			disembark=None
			yearam=None
			month=None
			day=None
			ship_name=None
			particular_outcome=None
		
		voyagedict={
			'id':v_id,
			'embarkation':embark,
			'disembarkation':disembark,
			'year':yearam,
			'month':month,
			'day':day,
			'ship_name':ship_name,
			'outcomes':{
				'particular_outcome':particular_outcome
			}
		}
					
		return PastEnslavedVoyageSerializer(voyagedict,many=False).data

	def get_enslavers(self,instance) -> ListField(child=EnslavedEnslaverSerializer()):
		edrs=instance.enslaved_relations.all()
		edrs=edrs.prefetch_related('relation__relation_enslavers__roles','relation__relation_enslavers__enslaver_alias__identity')
		enslaver_roles_and_identity_pks=edrs.values_list('relation__relation_enslavers__roles__id','relation__relation_enslavers__enslaver_alias__identity_id')
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
		return EnslavedEnslaverSerializer(enslavers_in_relation,many=True).data

	class Meta:
		model=Enslaved
# 		fields='__all__'
		exclude=[
# 			"documented_name",
# 			"name_first",
# 			"name_second",
# 			"name_third",
# 			"modern_name",
# 			"editor_modern_names_certainty",
# 			"age",
			"gender_int",
# 			"height",
# 			"skin_color",
# 			"dataset",
# 			"notes",
# 			"last_updated",
# 			"human_reviewed",
# 			"register_country",
# 			"last_known_date",
# 			'post_disembark_location',
# 			'captive_status',
# 			'language_group',
		]
#######################

#### FROM ENSLAVERS TO ENSLAVED


####################### ENSLAVERS M2M CONNECTIONS

#### FROM ENSLAVERS OUTWARDS
	
class EnslaverEnslavedSerializer(serializers.Serializer):
	id=serializers.IntegerField(required=True)
	documented_name=serializers.CharField(required=False,allow_null=True)
	class Meta:
		fields=('id','documented_name')

def fuzzyplacenamestrip(name):
	name=re.sub("(,\s*port unspecified)|(,\s*unspecified)|(\(colony unspecified\))|(,\s*place unspecified)","",name,re.I)
	return name

class EnslaverIdentitySerializer(serializers.ModelSerializer):
	names=serializers.SerializerMethodField(required=False)
	birth=serializers.SerializerMethodField(required=False)
	death=serializers.SerializerMethodField(required=False)
	principal_location=PastLocationSerializer(many=False,required=False,allow_null=True)
	named_enslaved_people=serializers.SerializerMethodField(required=False)
	voyages=serializers.SerializerMethodField(required=False)
	sources=serializers.SerializerMethodField(required=False)
	def get_names(self,instance) -> ListField(child=serializers.CharField(required=False)):
		aliases=instance.aliases.all()
		principal_alias=instance.principal_alias
		if aliases.count()>1:
			aliases=[a.alias for a in aliases]
			aliases=list(set(aliases))
		else:
			aliases=[principal_alias]
		return aliases
	
	def get_sources(self,instance) -> PastSourceSerializer(many=True):
		source_ids=list(set([i[0] for i in EnslaverIdentity.objects.all().filter(id=instance.id).values_list('aliases__enslaver_relations__relation__voyage__voyage_source_connections__source__id')]))
		sources=Source.objects.all().filter(id__in=source_ids)
		return PastSourceSerializer(sources,many=True).data



		escs=instance.enslaver_source_connections.all()
		sources_dict={}
		for esc in escs:
			page_range=esc.page_range
			s=esc.source
			s_id=s.id
			s.page_ranges=[page_range]
			if s_id not in sources_dict:
				sources_dict[s_id]=s
			else:
				sources_dict[s_id].page_ranges.append(page_range)
		return PastSourceSerializer([sources_dict[i] for i in sources_dict],many=True).data

	def get_named_enslaved_people(self,instance) -> EnslaverEnslavedSerializer(many=True):
		aliases=instance.aliases.all()
		aliases=aliases.prefetch_related(
			'alias__enslaver_relations__relation__enslaved_in_relation__enslaved'
		)
		enslaved_people_in_relation_tuples=aliases.values_list(
			'enslaver_relations__relation__enslaved_in_relation__enslaved__documented_name',
			'enslaver_relations__relation__enslaved_in_relation__enslaved__id'
		)
		enslaved_people_in_relation_dict={}
		for epirt in enslaved_people_in_relation_tuples:
			name,id=epirt
			if id not in enslaved_people_in_relation_dict and id is not None:
				enslaved_people_in_relation_dict[id]=name
		enslaved_people_in_relation=[{"id":k,"documented_name":enslaved_people_in_relation_dict[k]} for k in enslaved_people_in_relation_dict]
		return EnslaverEnslavedSerializer(enslaved_people_in_relation,many=True).data

	def get_voyages(self,instance) -> ListField(child=serializers.CharField(required=False)):
		voyages=Voyage.objects.filter(voyage_enslavement_relations__relation_enslavers__enslaver_alias__identity__id=instance.id)
		#dedupe
		voyage_ids=list(set([v.id for v in voyages]))
		voyages=Voyage.objects.filter(id__in=voyage_ids)
		#prefetch
		voyages=voyages.prefetch_related(
			'voyage_itinerary__imp_principal_place_of_slave_purchase',
			'voyage_itinerary__imp_principal_port_slave_dis',
			'voyage_dates__imp_arrival_at_port_of_dis_sparsedate'
		)
		voyagestrings=[]
		for v in voyages:
			embark=v.voyage_itinerary.imp_principal_place_of_slave_purchase
			if embark:
				embark=embark.name
				embark=fuzzyplacenamestrip(embark)
			else:
				embark="place unknown"
			disembark=v.voyage_itinerary.imp_principal_port_slave_dis
			if disembark:
				disembark=disembark.name
				disembark=fuzzyplacenamestrip(disembark)
			else:
				disembark="place unknown"
			yearam=v.voyage_dates.imp_arrival_at_port_of_dis_sparsedate
			if yearam:
				yearam=yearam.year
			else:
				yearam="year unknown"
			voyagestring=f"#{v.id}, {embark} to {disembark}, {yearam}"
			voyagestrings.append(voyagestring)
					
		return voyagestrings
	
	def get_birth(self,instance) -> serializers.CharField(required=False):
		birth_place=instance.birth_place
		year=instance.birth_year
		month=instance.birth_month
		day=instance.birth_day
		birth_date=pretty_date(month,day,year)
		return ", ".join([str(i) for i in [birth_place,birth_date] if i is not None])
	
	def get_death(self,instance) -> serializers.CharField(required=False):
		death_place=instance.death_place
		year=instance.death_year
		month=instance.death_month
		day=instance.death_day
		death_date=pretty_date(month,day,year)
		return ", ".join([str(i) for i in [death_place,death_date] if i is not None])

	class Meta:
		model=EnslaverIdentity
		fields=[
			'id',
			'birth',
			'death',
			'principal_location',
			'named_enslaved_people',
			'voyages',
			'sources',
			'names'
		]

############ REQUEST FIILTER OBJECTS
class EnslaverFilterItemSerializer(serializers.Serializer):
	@extend_schema_field({
		'oneOf': [
			{'type': 'string'},
			{'type': 'integer'},
			{'type': 'array'}
		]
	})
	def get_searchTerm(self, obj):
		return obj.searchTerm
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[
		k for k in EnslaverIdentity_options
	])
	searchTerm=serializers.SerializerMethodField(method_name='get_searchTerm')

class EnslavedFilterItemSerializer(serializers.Serializer):
	@extend_schema_field({
		'oneOf': [
			{'type': 'string'},
			{'type': 'integer'},
			{'type': 'array'}
		]
	})
	def get_searchTerm(self, obj):
		return obj.searchTerm
		
	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[
		k for k in Enslaved_options
	])
	searchTerm=serializers.SerializerMethodField(method_name='get_searchTerm')

class EnslavementRelationFilterItemSerializer(serializers.Serializer):
	@extend_schema_field({
		'oneOf': [
			{'type': 'string'},
			{'type': 'integer'},
			{'type': 'array'}
		]
	})
	def get_searchTerm(self, obj):
		return obj.searchTerm

	op=serializers.ChoiceField(choices=["in","gte","lte","exact","icontains","btw","andlist"])
	varName=serializers.ChoiceField(choices=[
		k for k in EnslavementRelation_options
	])
	searchTerm=serializers.SerializerMethodField(method_name='get_searchTerm')




########### PAGINATED ENSLAVED LISTS 
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated, filtered list of enslaved people',
			summary='Paginated, filtered list of enslaved people',
			description='Here, we request page 2 (with 5 items per page) of enslaved people who were recorded as between 5-15 years of age when their information was recorded.',
			value={
			  "filter": [
					{
						"varName":"age",
						"searchTerm":[5,15],
						"op":"btw"
					}
				],
				"page": 2,
				"page_size": 5
			},
			request_only=True
		)
    ]
)
class EnslavedListRequestSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False)
	page_size=serializers.IntegerField(required=False)
	filter=EnslavedFilterItemSerializer(many=True,required=False)
	order_by=serializers.ListField(child=serializers.CharField(required=False),required=False)
	global_search=serializers.CharField(required=False)

class EnslavedListResponseSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False)
	page_size=serializers.IntegerField(required=False)
	count=serializers.IntegerField(required=False)
	results=EnslavedSerializer(many=True,allow_null=True)

########### PAGINATED ENSLAVER LISTS 
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated, filtered list of enslavers',
			summary='Paginated request for filtered voyages.',
			description='Here, we request page 2 (with 5 items per page) of enslavers who are associated with voyages that disembarked captives between 1820-1830 in Cuba.',
			value={
			  "filter": [
					{
						"varName":"aliases__enslaver_relations__relation__voyage__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"searchTerm":[1820,1830],
						"op":"btw"
					},
					{
						"varName":"aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__name",
						"searchTerm":["Cuba"],
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
class EnslaverListRequestSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False)
	page_size=serializers.IntegerField(required=False)
	filter=EnslaverFilterItemSerializer(many=True,required=False)
	order_by=serializers.ListField(child=serializers.CharField(required=False),required=False)
	global_search=serializers.CharField(required=False)
	
class EnslaverListResponseSerializer(serializers.Serializer):
	page=serializers.IntegerField(required=False)
	page_size=serializers.IntegerField(required=False)
	count=serializers.IntegerField(required=False)
	results=EnslaverIdentitySerializer(many=True,allow_null=True)

############ AUTOCOMPLETE SERIALIZERS
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated autocomplete on enslaver aliases',
			summary='Paginated autocomplete on enslaver aliases',
			description='Here, we are requesting 5 suggested values, starting with the 10th item, of enslaver aliases (names) like "george" associated with voyages that disembarked captives between the years 1820-40.',
			value={
				"varName": "aliases__alias",
				"querystr": "george",
				"offset": 10,
				"limit": 5,
				"filter": [
					{
						"varName": "aliases__enslaver_relations__relation__voyage__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"op": "btw",
						"searchTerm": [1820,1840]
					}
				]
			},
			request_only=True
		)
    ]
)
class EnslaverAutoCompleteRequestSerializer(serializers.Serializer):
	varName=serializers.CharField(required=False)
	querystr=serializers.CharField(required=False)
	offset=serializers.IntegerField(required=False)
	limit=serializers.IntegerField(required=False)
	filter=EnslaverFilterItemSerializer(many=True,required=False)
	global_search=serializers.CharField(required=False)

class EnslaverAutoCompletekvSerializer(serializers.Serializer):
	value=serializers.CharField(required=False)

class EnslaverAutoCompleteResponseSerializer(serializers.Serializer):
	suggested_values=EnslaverAutoCompletekvSerializer(many=True,allow_null=True)
	
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Paginated autocomplete on enslaved names',
			summary='Paginated filtered autocomplete on enslaved names',
			description='Here, we are requesting the first 5 suggested values, of the recorded names of enslaved people, when those names are like "george", for records entered in the "Intra-American" enslaved dataset(s)',
			value={
				"varName": "documented_name",
				"querystr": "george",
				"offset": 0,
				"limit": 5,
				"filter": [
					{
						"varName":"dataset",
						"op":"exact",
						"searchTerm":0
					}
				]
			},
			request_only=True
		)
    ]
)
class EnslavedAutoCompleteRequestSerializer(serializers.Serializer):
	varName=serializers.CharField(required=False)
	querystr=serializers.CharField(required=False)
	offset=serializers.IntegerField(required=False)
	limit=serializers.IntegerField(required=False)
	filter=EnslavedFilterItemSerializer(many=True,required=False)
	global_search=serializers.CharField(required=False)

class EnslavedAutoCompletekvSerializer(serializers.Serializer):
	value=serializers.CharField(required=False)

class EnslavedAutoCompleteResponseSerializer(serializers.Serializer):
	suggested_values=EnslavedAutoCompletekvSerializer(many=True,allow_null=True)

############ AGGREGATION ON FIELDS
@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Filtered request for min/max',
			summary='Filtered request for min/max',
			description='Here, we request the min and max year on which enslaved individuals whose names we know disembarked from a voyage.',
			value={
				"varName": "enslaved_relations__relation__voyage__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
				"filter": [
				]
			},
			request_only=True
		)
    ]
)
class EnslavedFieldAggregationRequestSerializer(serializers.Serializer):
	varName=serializers.CharField(required=False)

class EnslavedFieldAggregationResponseSerializer(serializers.Serializer):
	varName=serializers.CharField(required=False)

	min=serializers.IntegerField(required=False)
	max=serializers.IntegerField(required=False)

@extend_schema_serializer(
	examples = [
         OpenApiExample(
			'Filtered request for min/max',
			summary='Filtered request for min/max',
			description='Here, we request the min and max year on which voyages that we have named enslavers listed for',
			value={
				"varName": "aliases__enslaver_relations__relation__voyage__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
				"filter": [
				]
			},
			request_only=True
		)
    ]
)
class EnslaverFieldAggregationRequestSerializer(serializers.Serializer):
	varName=serializers.CharField(required=False)
	
class EnslaverFieldAggregationResponseSerializer(serializers.Serializer):
	varName=serializers.CharField(required=False)
	min=serializers.IntegerField(required=False)
	max=serializers.IntegerField(required=False)

############ DATAFRAMES ENDPOINTS
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered request for 2 columns',
			summary="Filtered req for 2 cols",
			description="Here, we are looking for the enslaved person\'s documented name, and the region in which they disembarked, for individuals whose names we know who were transported between 1810-15.",
			value={
				"selected_fields":[
					"documented_name",
					"enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__name"
				],
				"filter":[
					{
						"varName": "enslaved_relations__relation__voyage__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"op": "btw",
						"searchTerm": [1810,1815]
					}
				]
			}
		)
	]
)
class EnslavedDataframesRequestSerializer(serializers.Serializer):
	selected_fields=serializers.ListField(
		child=serializers.ChoiceField(choices=[
			k for k in Enslaved_options
		])
	)
	filter=EnslavedFilterItemSerializer(many=True,required=False,allow_null=True)
	global_search=serializers.CharField(required=False)

@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered request for 2 columns',
			summary="Filtered req for 2 cols",
			description="Here, we are looking for the name and date of birth for enslavers associated with voyages to Barbados.",
			value={
				"selected_fields":[
					"birth_year",
					"principal_alias"
				],
				"filter":[
					{
						"varName": "aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__name",
						"op": "in",
						"searchTerm": ["Barbados"]
					}
				]
			}
		)
	]
)
class EnslaverDataframesRequestSerializer(serializers.Serializer):
	selected_fields=serializers.ListField(
		child=serializers.ChoiceField(choices=[
			k for k in EnslaverIdentity_options
		])
	)
	filter=EnslaverFilterItemSerializer(many=True,required=False)
	global_search=serializers.CharField(required=False)


@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'Filtered request for 3 columns',
			summary="Filtered req for 3 cols",
			description="Here, we are looking for the enslaved person\'s documented name, the ship's name, and the pk of the relation for people who were transported between 1810-15.",
			value={
				"selected_fields":[
					"id",
					"voyage__voyage_ship__ship_name",
					"enslaved_in_relation__enslaved__documented_name"
				],
				"filter":[
					{
						"varName": "voyage__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
						"op": "btw",
						"searchTerm": [1810,1815]
					}
				]
			}
		)
	]
)
class EnslavementRelationDataframesRequestSerializer(serializers.Serializer):
	selected_fields=serializers.ListField(
		child=serializers.ChoiceField(choices=[
			k for k in EnslavementRelation_options
		])
	)
	filter=EnslavementRelationFilterItemSerializer(many=True,required=False)
	global_search=serializers.CharField(required=False)

############ GEOTREE REQUESTS
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			"Filtered req for enslaved people geo vals",
			summary="Filtered req for enslaved people geo vals",
			description="Here, we are looking for a tree of all the values used for the 'port of departure' variable for named enslaved individuals who were disembarked in Texas.",
			value={
				"geotree_valuefields":["enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_place_of_slave_purchase__value"],
				"filter":[
					{
						"varName": "enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__name",
						"op": "in",
						"searchTerm": ["Texas"]
					}
				]
			}
		)
	]
)
class EnslavedGeoTreeFilterRequestSerializer(serializers.Serializer):
	geotree_valuefields=serializers.ListField(
		child=serializers.ChoiceField(
			choices=[
				k for k in Enslaved_options
				if (("post_disembark_location" in k or "voyage_itinerary" in k) and k.endswith("value"))
			]
		)
	)
	filter=EnslavedFilterItemSerializer(many=True,required=False,allow_null=True)
	global_search=serializers.CharField(required=False)
	

############ GEOTREE REQUESTS
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			"Filtered req for enslaver geo vals",
			summary="Filtered req for enslaver geo vals",
			description="Here, we are looking for a tree of all the values used for the 'port of departure' variable (used for tracking the triangular trade) for enslavers who are associated with Intra-American voyages.",
			value={
				"geotree_valuefields":["aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_port_voyage_begin__value"],
				"filter":[
					{
						"varName": "aliases__enslaver_relations__relation__voyage__dataset",
						"op": "exact",
						"searchTerm": 1
					}
				]
			}
		)
	]
)
class EnslaverGeoTreeFilterRequestSerializer(serializers.Serializer):
	geotree_valuefields=serializers.ListField(
		child=serializers.ChoiceField(
			choices=[
				k for k in EnslaverIdentity_options
				if (("voyage_itinerary" in k or "place" in k) and k.endswith("value"))
			]
		)
	)
	filter=EnslaverFilterItemSerializer(many=True,required=False,allow_null=True)
	global_search=serializers.CharField(required=False)
	
	
############ PAST AGGREGATION ROUTE MAPS
@extend_schema_serializer(
	examples=[
		OpenApiExample(
			'filtered request for people disembarked in barbados',
			summary="Filtered request for people disembarked in Barbados",
			description="Here we request the routes taken by enslaved individuals whose names we know who disembarked in Barbados (in this case, only one individual, Broteer Furro).",
			value={
				"zoomlevel": "region",
				"filter":[
					{
						"varName":"enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__name",
						"op":"in",
						"searchTerm":["Barbados, place unspecified"]
					}
				]
			}
		)
	]

)
class EnslavedAggRoutesRequestSerializer(serializers.Serializer):
	zoomlevel=serializers.ChoiceField(choices=(('region','region'),('place','place')))
	filter=EnslavedFilterItemSerializer(many=True,required=False,allow_null=True)
	global_search=serializers.CharField(required=False)

class EnslavedAggRoutesEdgesSerializer(serializers.Serializer):
	source=serializers.CharField(required=False)
	target=serializers.CharField(required=False)
	type=serializers.CharField(required=False)
	weight=serializers.IntegerField(required=False)
	controls=serializers.ListField(child=serializers.ListField(child=serializers.FloatField(allow_null=True)),required=False)

class EnslavedAggRoutesNodesDataSerializer(serializers.Serializer):
	lat=serializers.FloatField(allow_null=False,required=False)
	lon=serializers.FloatField(allow_null=False,required=False)
	name=serializers.CharField(required=False)
	tags=serializers.ListField(child=serializers.CharField(required=False),required=False)

class EnslavedAggRoutesNodesWeightsSerializer(serializers.Serializer):
	disembarkation=serializers.IntegerField(required=False)
	embarkation=serializers.IntegerField(required=False)
	origin=serializers.IntegerField(required=False)
	post_disembarkation=serializers.IntegerField(required=False)

class EnslavedAggRoutesNodesSerializer(serializers.Serializer):
	id=serializers.CharField(required=False)
	weights=EnslavedAggRoutesNodesWeightsSerializer()
	data=EnslavedAggRoutesNodesDataSerializer()
	
class EnslavedAggRoutesResponseSerializer(serializers.Serializer):
	edges=serializers.ListField(child=EnslavedAggRoutesEdgesSerializer())
	nodes=serializers.ListField(child=EnslavedAggRoutesNodesSerializer())

############### NETWORK GRAPHS

@extend_schema_serializer(
	examples=[
		OpenApiExample(
			"Connections to Robert N. Henderson",
			summary="Connections to Robert N. Henderson",
			description="Here we request the connections to enslaver #55232, Robert N. Henderson.",
			value={
				"enslavers": [55232]
			}
		)
	]
)
class PASTNetworksRequestSerializer(serializers.Serializer):
	enslaved=serializers.ListField(
		child=serializers.IntegerField(required=False), required=False
	)
	enslavers=serializers.ListField(
		child=serializers.IntegerField(required=False), required=False
	)
	voyages=serializers.ListField(
		child=serializers.IntegerField(required=False), required=False
	)
	enslavement_relations=serializers.ListField(
		child=serializers.IntegerField(required=False), required=False
	)

class PASTNetworksResponseNodeSerializer(serializers.Serializer):
	id=serializers.IntegerField(required=False)
	node_class=serializers.CharField(required=False)
	uuid=serializers.CharField(required=False)
	data=serializers.JSONField(required=False)

class PASTNetworksResponseEdgeSerializer(serializers.Serializer):
	source=serializers.CharField(required=False)
	target=serializers.CharField(required=False)
	data=serializers.JSONField(required=False)
	
class PASTNetworksResponseSerializer(serializers.Serializer):
	nodes=PASTNetworksResponseNodeSerializer(many=True,allow_null=True)
	edges=PASTNetworksResponseEdgeSerializer(many=True,allow_null=True)

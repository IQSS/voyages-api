from voyage.models import Voyage,VoyageShip
from past.models import EnslaverAlias,Enslaved
from blog.models import Post
from document.models import Source

#we need an index of
#a. highly-nested related fields
#b. that need to be searched
#c. and have fewer than, say, 100 entries
#to capture that we need to know:
#Target Model, Source Model, & related field name (that is, how do you get from the target to the source)
#e.g., I get to the "particular outcome" of a voyage from the enslaved people model via enslaved_relations__relation__voyage__voyage_outcome__particular_outcome__name
autocomplete_basic_index_field_endings=[
	('Tag','Post','tags__name'),
	('Author','Post','authors__name'),
	('Post','Post','title'),
	('Nationality','Voyage','voyage_ship__nationality_ship__name'),
	('RigOfVessel','Voyage','voyage_ship__rig_of_vessel__name'),
	('CargoType','Voyage','voyage_ship__cargo__name'),
	('AfricanInfo','Voyage','african_info__name'),
	('TonType','Voyage','ton_type__name'),
	('ParticularOutcome','Voyage','voyage_outcome__particular_outcome__name'),
	('SlavesOutcome','Voyage','voyage_outcome__outcome_slaves__name'),
	('VesselCapturedOutcome','Voyage','voyage_outcome__vessel_captured_outcome__name'),
	('OwnerOutcome','Voyage','voyage_outcome__outcome_owner__name'),
	('Resistance','Voyage','voyage_outcome__resistance__name'),
	('CaptiveFate','Enslaved','captive_fate__name'),
	('ParticularOutcome','Enslaved','enslaved_relations__relation__voyage__voyage_outcome__particular_outcome__name'),
	('Source','Enslaved','enslaved_source_connections__source__title'),
	('EnslaverRole','EnslaverIdentity','aliases__enslaver_relations__roles__name'),
	('LanguageGroup','Enslaved','language_group__name')
]

#there are more complex indices that need to be pushed into solr
#a. highly-nested related fields
#b. that need to be searched
#c. and have many entries
#to capture that, we need to know
#i. the Target Model that these related field(S) reside in
#ii. the fields that we want to index (starting with the pk)
#iii. the Source Model we want to get to these fields from
#iv. and the paths by which we get there, relationally
#v. and the solr core to dump it into
#e.g., we can search ship names related to documentary sources by
#1. selecting the VoyageShip model
#2. targeting the Source model
#e. getting there via source_voyage_connections__voyage__voyage_ship__ship_name
autocomplete_indices=[
	{
		#target model
		"model":EnslaverAlias,
		#solr 
		"core_name":"autocomplete_enslaver_aliases",
		#indexed fields
		"fields":[
			'id',
			'alias',
			'identity__principal_alias'
		],
		#source model & ORM path
		"related_fields":[
			('Enslaved','enslaved_relations__relation__relation_enslavers__enslaver_alias__alias'),
			('Voyage','voyage__voyage_enslaver_connection__enslaver_alias__alias'),
			('Voyage','voyage_enslavement_relations__relation_enslavers__enslaver_alias__alias'),
			('EnslaverIdentity','aliases__alias'),
			('EnslaverIdentity','voyage_enslavement_relations__relation_enslavers__enslaver_alias__alias'),
		]
	},
	{
		"model":Enslaved,
		"core_name":"autocomplete_enslaved_names",
		"fields":[
			'enslaved_id',
			'documented_name',
			'modern_name'
		],
		"related_fields":[
			('EnslaverIdentity','aliases__enslaver_relations__relation__enslaved_in_relation__enslaved__documented_name'),
			('EnslaverIdentity','aliases__enslaver_relations__relation__enslaved_in_relation__enslaved__modern_name'),
			('Voyage','voyage_enslavement_relations__enslaved_in_relation__enslaved__documented_name'),
			('Voyage','voyage_enslavement_relations__enslaved_in_relation__enslaved__modern_name'),
			('Enslaved','modern_name'),
			('Enslaved','documented_name')
		]
	},
	{
		"model":Source,
		"core_name":"autocomplete_source_titles",
		"fields":[
			'id',
			'title',
			'short_ref__name'
		],
		"related_fields":[
			('Enslaved','enslaved_source_connections__source__title'),
			('EnslaverIdentity','enslaver_source_connections__source__title'),
			('EnslaverIdentity','aliases__enslaver_relations__relation__voyage__voyage_source_connections__source__title'),
			('Voyage','voyage_source_connections__source__title'),
			
			('Enslaved','enslaved_source_connections__source__short_ref__name'),
			('EnslaverIdentity','enslaver_source_connections__source__short_ref__name'),
			('EnslaverIdentity','aliases__enslaver_relations__relation__voyage__voyage_source_connections__source__short_ref__name'),
			('Voyage','voyage_source_connections__source__short_ref__name'),
			
			('Enslaved','enslaved_source_connections__source__page_connections__page__transcriptions__text'),
			('EnslaverIdentity','enslaver_source_connections__source__page_connections__page__transcriptions__text'),
			('EnslaverIdentity','aliases__enslaver_relations__relation__voyage__voyage_source_connections__source__page_connections__page__transcriptions__text'),
			('Voyage','voyage_source_connections__source__page_connections__page__transcriptions__text')
		]
	},
	{
		"model":VoyageShip,
		"core_name":"autocomplete_ship_names",
		"fields":[
			'id',
			'ship_name'
		],
		"related_fields":[
			('Voyage','voyage_ship__ship_name'),
			('EnslaverIdentity','aliases__enslaver_relations__relation__voyage__voyage_ship__ship_name'),
			('Enslaved','enslaved_relations__relation__voyage__voyage_ship__ship_name'),
			('Source','source_voyage_connections__voyage__voyage_ship__ship_name')
		]
	}
]

def get_inverted_autocomplete_indices():
	inverted_autocomplete_indices={
		field:{
			'model':ac_index['model'],
			'core_name':ac_index['core_name'],
			'fields':ac_index['fields'][1]
		}
		for ac_index in autocomplete_indices for field in ac_index['related_fields']
	}
	return inverted_autocomplete_indices

def get_inverted_autocomplete_basic_index_field_endings():
	inverted_autocomplete_basic_index_field_endings={}
	for t in autocomplete_basic_index_field_endings:
		target,source,rfname=t
		if source not in inverted_autocomplete_basic_index_field_endings:
			inverted_autocomplete_basic_index_field_endings[source]={rfname:target}
		else:
			inverted_autocomplete_basic_index_field_endings[source][rfname]=target
	return inverted_autocomplete_basic_index_field_endings

def get_all_model_autocomplete_fields(modelname):
	model_autocomplete_fields=[]
	for t in autocomplete_basic_index_field_endings:
		target,source,rfname=t
		if source==modelname and rfname not in model_autocomplete_fields:
			model_autocomplete_fields.append(rfname)
	for ac_index in autocomplete_indices:
		related_fields=ac_index['related_fields']
		for rf in ac_index['related_fields']:
			rfmodel,field=rf
			if modelname==rfmodel:
				if field not in model_autocomplete_fields:
					model_autocomplete_fields.append(field)
	return(model_autocomplete_fields)
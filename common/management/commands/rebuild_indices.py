import requests
import json
from django.core.management.base import BaseCommand, CommandError
from voyage.models import Voyage
from past.models import EnslaverIdentity,Enslaved
from blog.models import Post
from document.models import Source
import pysolr
import numpy as np
from voyages3.localsettings import SOLR_ENDPOINT

class Command(BaseCommand):
	help = 'rebuilds the solr indices'
	def handle(self, *args, **options):
		indices=[
			{
				"model":Voyage,
				"core_name":"voyages",
				"fields":[
					"id",
					"voyage_itinerary__imp_principal_region_slave_dis__name",
					"voyage_itinerary__region_of_return__name",
					"voyage_itinerary__imp_port_voyage_begin__name",
					"voyage_itinerary__imp_region_voyage_begin__name",
					"voyage_itinerary__imp_principal_place_of_slave_purchase__name",
					"voyage_itinerary__imp_principal_region_of_slave_purchase__name",
					"voyage_itinerary__imp_principal_port_slave_dis__name",
					"voyage_enslavement_relations__relation_enslavers__enslaver_alias__alias",
					"voyage_ship__ship_name"
				]
			},
			{
				"model":EnslaverIdentity,
				"core_name":"enslavers",
				"fields":[
					'id',
					'principal_location__name',
					'aliases__enslaver_relations__relation__enslaved_in_relation__enslaved__documented_name',
					'aliases__alias',
					'birth_place__name',
					'death_place__name',
					'principal_alias',
					'father_name',
					'father_occupation',
					'mother_name',
					'notes'
				]
			},
			{
				"model":Enslaved,
				"core_name":"enslaved",
				"fields":[
					'id',
					'documented_name',
					'name_first',
					'name_second',
					'name_third',
					'modern_name',
					'notes'
				]
			},
			{
				"model":Post,
				"core_name":"blog",
				"fields":[
					'id',
					'authors__name',
					'authors__description',
					'authors__role',
					'tags__name',
					'tags__intro',
					'title',
					'subtitle',
					'content'
				]
			},
			{
				"model":Source,
				"core_name":"sources",
				"fields":[
					'id',
					'title',
					'short_ref__name',
					'page_connections__page__transcriptions__text'
				]
			},
			{
				"model":Voyage,
				"core_name":"voyagesources",
				"fields":[
					'id',
					'voyage_source_connections__source__bib',
					'voyage_source_connections__source__short_ref__name'
				]
			},
			{
				"model":Enslaved,
				"core_name":"enslavedsources",
				"fields":[
					'id',
					'enslaved_relations__relation__voyage__voyage_source_connections__source__bib',
					'enslaved_relations__relation__voyage__voyage_source_connections__source__short_ref__name'
				]
			},
			{
				"model":EnslaverIdentity,
				"core_name":"enslaversources",
				"fields":[
					'id',
					'enslaver_source_connections__source__bib',
					'enslaver_source_connections__source__short_ref__name',
					'aliases__enslaver_relations__relation__voyage__voyage_source_connections__source__bib',
					'aliases__enslaver_relations__relation__voyage__voyage_source_connections__source__short_ref__name'
				]
			}
		]
		
		results_per_page=1000
		
		for idx in indices:
			
			model=idx["model"]
			fields=idx["fields"]
			core_name=idx["core_name"]
			print("INDEXING",core_name,"on",len(fields),"fields")
			
			if fields[0]!="id":
				print("FIRST FIELD INDEX MUST BE NAMED `ID`")
				exit()

			solr = pysolr.Solr(
				f'{SOLR_ENDPOINT}/{core_name}/',
				always_commit=True,
				timeout=10
			)
			
			queryset=model.objects.all()
			if core_name=="sources":
				queryset=queryset.filter(has_published_manifest=True)
			
			ids=[i[0] for i in queryset.values_list('id')]
			
			if len(ids)>0:
			
				batch_size=5000
			
				pagecount=int(len(ids)/batch_size)
				if pagecount==0:
					pagecount=1
				
				pages=np.array_split(np.array(ids),pagecount)
			
				p=1
			
				for page in pages:
					print("--page",p,'of',pagecount)
				
					pageidlist=[int(v) for v in page]
				
					pagedict={v:[] for v in pageidlist}
				
					pagequeryset=queryset.filter(id__in=pageidlist)
				
					for f in fields:
						vl=pagequeryset.values_list('id',f)
						for v in vl:
							id,i=v
							if i!=None:
								pagedict[id].append(str(i))
				
					solrpage=[
						{
							"id":k,
							"text":" ".join(pagedict[k])
						}
						for k in pagedict
					]
				
					solr.add(solrpage)
					p+=1
			else:
				print("-----FOUND NO RESULTS----")
import requests
import json
from django.core.management.base import BaseCommand, CommandError
from voyage.models import Voyage,VoyageShip
from past.models import EnslaverAlias,Enslaved
from blog.models import Post
from document.models import Source
import pysolr
import numpy as np
from voyages3.localsettings import SOLR_ENDPOINT
from common.autocomplete_indices import autocomplete_indices

class Command(BaseCommand):
	help = 'rebuilds the solr indices'
	def handle(self, *args, **options):
		for idx in autocomplete_indices:
			model=idx["model"]
			fields=idx["fields"]
			if fields[0] != 'id':
				print("FIRST INDEXED FIELD MUST BE INTEGER PK ('id')")
			
			core_name=idx["core_name"]
			print("INDEXING",core_name,"on",len(fields),"fields")
			solr = pysolr.Solr(
				f'{SOLR_ENDPOINT}/{core_name}/',
				always_commit=True,
				timeout=10
			)
			queryset=model.objects.all()
			if queryset.count()>0:
				#here, we're not interested in id's per se but rather the unique text values
				valtuples=list(eval('queryset.values_list("'+'","'.join(fields)+'")'))
				indexdictionary={}
				solrindex=[]
				#so for our reference we'll just keep one good id for each unique str value
				for valtuple in valtuples:
					id=valtuple[0]
					valstr=' '.join([v for v in valtuple[1:] if v is not None])
					indexdictionary[valstr]=id
				for k in indexdictionary:
					solrindex.append({"id":indexdictionary[k],"text":k})
				solr.add(solrindex)
			else:
				print("-----FOUND NO RESULTS----")
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
				
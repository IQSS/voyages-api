from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.template import loader
from django.shortcuts import redirect,render
from django.core.paginator import Paginator
from django.shortcuts import render,get_object_or_404
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from django.views.generic.list import ListView
from collections import Counter
import urllib
import json
import requests
import time
from .models import *
import pprint
from common.reqs import *
import pysolr
import collections
import gc
from .serializers import *
from voyages3.localsettings import REDIS_HOST,REDIS_PORT,DEBUG,GEO_NETWORKS_BASE_URL,PEOPLE_NETWORKS_BASE_URL,USE_REDIS_CACHE
import re
import redis
import hashlib
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from common.static.Source_options import Source_options
from rest_framework import filters

redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

class DocumentSearch(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		request=DocumentSearchSerializer,
		responses=SourceListResponseSerializer
	)
	
	def post(self,request):
		st=time.time()
		print("DOCUMENT SEARCH+++++++\nusername:",request.auth.user)
		
		
		
		#VALIDATE THE REQUEST
		serialized_req = DocumentSearchSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		srd=serialized_req.data
		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		if USE_REDIS_CACHE:
			hashdict={
				'req_name':str(self.request),
				'req_data':srd
			}
			hashed=hashlib.sha256(json.dumps(hashdict,sort_keys=True,indent=1).encode('utf-8')).hexdigest()
			cached_response = redis_cache.get(hashed)
		else:
			cached_response=None
			
		

		def solrfilter(queryset,core_name,search_string):
			
			if type(search_string)!=list:
				search_list=[search_string]
			else:
				search_list=search_string
			
			for search_string in search_list:
				print("SEARCH STRING",search_string)
				solr = pysolr.Solr(
						f'{SOLR_ENDPOINT}/{core_name}/',
						always_commit=True,
						timeout=10
					)
				searchstringcomponents=[''.join(filter(str.isalnum,s)) for s in search_string.split(' ')]
				finalsearchstring="(%s)" %(" ").join(searchstringcomponents)
				results=solr.search('text:%s' %finalsearchstring,**{'rows':10000000,'fl':'id'})
				ids=[doc['id'] for doc in results.docs]
				
				queryset=queryset.filter(id__in=ids)
				
			return queryset
		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Source.objects.all()
			queryset=queryset.filter(has_published_manifest=True)
			
			voyage_ids=srd.get('voyageIds')
			if voyage_ids is not None:
				voyage_ids_clean=[int(i) for i in re.findall("[0-9]+",str(voyage_ids))]
				if voyage_ids_clean:
					for voyage_id in voyage_ids_clean:
						queryset=queryset.filter(source_voyage_connections__voyage_id=voyage_id)
			
			source_title=srd.get('title')
			if source_title is not None:
				queryset=queryset.filter(title__icontains=source_title)
				print("TITLE",source_title,queryset.count())
			
			bib=srd.get('bib')
			if bib is not None:
				queryset=queryset.filter(bib__icontains=bib)
				print("BIB",bib,queryset.count())
			
			enslavers=srd.get('enslavers')
			if enslavers is not None:
				print("ENSLAVERS",enslavers,queryset.count())
				queryset=solrfilter(queryset,'enslavers',enslavers)
			
			fulltext=srd.get("fullText")
			if fulltext is not None:
				print("FULLTEXT",fulltext,queryset.count())
				queryset=solrfilter(queryset,'sources',fulltext)
			
			if queryset.count()>0:
			
				ids=[i[0] for i in queryset.values_list('id')]
				
				request=dict(request.data)
				request['filter']=[
					{
						'varName':'id',
						'op':'in',
						'searchTerm':ids,
					}
				]
				
				results,results_count,page,page_size,error_messages=post_req(	
					queryset,
					self,
					request,
					Source_options,
					auto_prefetch=True,
					paginate=True
				)
				
				if error_messages:
					return(JsonResponse(error_messages,safe=False,status=400))

				
			else:
				results=[]
				results_count=0
				page=1
				page_size=0
							
			
			resp=SourceListResponseSerializer({
				'count':results_count,
				'page':page,
				'page_size':page_size,
				'results':results
			}).data
			
# 			print(len(resp))
# 			print(resp)
			#I'm having the most difficult time in the world validating this nested paginated response
			#And I cannot quite figure out how to just use the built-in paginator without moving to urlparams
			#SAVE THIS NEW RESPONSE TO THE REDIS CACHE
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,json.dumps(resp))
		else:
			resp=json.loads(cached_response)
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")

		return JsonResponse(resp,safe=False,status=200)

class SourceList(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		request=SourceRequestSerializer,
		responses=SourceResponseSerializer
	)
	
	def post(self,request):
		'''
		Voyages has always been built on scholarship, with references to many different archival sources. In the legacy version of the site, the sources were organized with a unique short reference ("short_ref") and a full reference ("full_ref"), like OMNO & Outward Manifests for New Orleans. When these sources were connected to Voyages, they would oftentimes be connected along with a field called "text_ref" that pointed at a specific location in the archive, or page number in the book.
		
		In this new build, we have moved all of our sources over to Zotero where they can be cleaned up -- the data got messy over the years, because bibliographical data is notoriously difficult to format. We now effectively have 2 unique keys: a Zotero ID and a "short_ref". We have also created records for individual pages that point at these new sources, because our work with several libraries on the South Seas Co. documents for an NEH grant means that we have images and page-level data for some new sources, allowing for unprecedented granularity in our work with archives.
		
		These changes necessitated that we create Docs as its own django app and endpoint. Now, each "Source" points at one or more Voyages, Enslaved People, or Enslavers. In turn, some of these Sources also have page-level metadata and links to IIIF images. For more information on the IIIF specification, visit https://iiif.io/api/index.html
		'''
		st=time.time()
		print("SOURCE LIST+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = SourceRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		if USE_REDIS_CACHE:
			srd=serialized_req.data
			hashdict={
				'req_name':str(self.request),
				'req_data':srd
			}
			hashed=hashlib.sha256(json.dumps(hashdict,sort_keys=True,indent=1).encode('utf-8')).hexdigest()
			cached_response = redis_cache.get(hashed)
		else:
			cached_response=None
			
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Source.objects.all()
			queryset=queryset.order_by('id')
			results,results_count,page,page_size,error_messages=post_req(	
				queryset,
				self,
				request,
				Source_options,
				auto_prefetch=True,
				paginate=True
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			resp=SourceListResponseSerializer({
				'count':results_count,
				'page':page,
				'page_size':page_size,
				'results':results
			}).data
			
# 			print(len(resp))
# 			print(resp)
			#I'm having the most difficult time in the world validating this nested paginated response
			#And I cannot quite figure out how to just use the built-in paginator without moving to urlparams
			#SAVE THIS NEW RESPONSE TO THE REDIS CACHE
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,json.dumps(resp))
		else:
			resp=json.loads(cached_response)
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")

		return JsonResponse(resp,safe=False,status=200)

####################### CLASSIC DJANGO TEMPLATED VIEWS -- KILL THESE AS SOON AS THE CONTRIBUTE FORM IS WORKING
# default view will be a paginated gallery
@extend_schema(
		exclude=True
	)
def Gallery(request,collection_id=None,pagenumber=1):
	
	if request.user.is_authenticated:
		
		#let's only get the zotero objects that have pages
		#otherwise, no need for the gallery -- and it lards the gallery up
		sources=Source.objects.order_by().all().filter(~Q(page_connections=None))
		
		other_collections=[]
		page_collection_id=None
		page_collection_label="No Collection Selected"
		for collection_tuple in sources.values_list(
			"short_ref__id",
			"short_ref__name"
		).distinct():
			this_collection_id,this_collection_label=collection_tuple
			if this_collection_id==collection_id:
				print(this_collection_id,this_collection_label)
				page_collection_label=this_collection_label
				page_collection_id=this_collection_id
			else:
				other_collections.append({
					"id":this_collection_id,
					"label":this_collection_label
				})
			
		sources=sources.filter(short_ref__id=collection_id).distinct()
		sources=sources.order_by('id')
		sources_paginator=Paginator(sources, 12)
		this_page=sources_paginator.get_page(pagenumber)
		
		return render(
			request,
			"gallery.html",
			{
				"page_collection_label":page_collection_label,
				"page_obj": this_page,
				"other_collections":other_collections,
				"page_collection_id":page_collection_id
			}
		)
	else:
		return HttpResponseForbidden("Forbidden")

class SourceCharFieldAutoComplete(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The autocomplete endpoints provide paginated lists of values on fields related to the endpoints primary entity (here, documentary sources). It also accepts filters. This means that you can apply any filter you would to any other query, for instance, the sources list view, in the process of requesting your autocomplete suggestions, thereby rapidly narrowing your search.",
		request=SourceAutoCompleteRequestSerializer,
		responses=SourceAutoCompleteResponseSerializer,
	)
	def post(self,request):
		st=time.time()
		print("Source CHAR FIELD AUTOCOMPLETE+++++++\nusername:",request.auth.user)
		#VALIDATE THE REQUEST
		serialized_req = SourceAutoCompleteRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		
		srd=serialized_req.data
		if USE_REDIS_CACHE:
			hashdict={
				'req_name':str(self.request),
				'req_data':srd
			}
			hashed_full_req=hashlib.sha256(json.dumps(hashdict,sort_keys=True,indent=1).encode('utf-8')).hexdigest()
			cached_response = redis_cache.get(hashed_full_req)
		else:
			cached_response=None

		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#But first let's see if this autocomplete request has been run before (other than the exact letters typed in...)
						
			unfiltered_queryset=Source.objects.all()
			
			final_vals=autocomplete_req(unfiltered_queryset,self,request,Source_options,'Source')
			
			#RUN THE AUTOCOMPLETE ALGORITHM
			
			resp=dict(request.data)
			resp['suggested_values']=final_vals
			#VALIDATE THE RESPONSE
			serialized_resp=SourceAutoCompleteResponseSerializer(data=resp)
			#SAVE THIS NEW RESPONSE TO THE REDIS CACHE
			if USE_REDIS_CACHE:
				redis_cache.set(hashed_full_req,json.dumps(resp))
		else:
			if DEBUG:
				print("cached:",hashed_full_req)
			resp=json.loads(cached_response)
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
		return JsonResponse(resp,safe=False,status=200)

# then the individual page view
@extend_schema(
		exclude=True
	)
def source_page(request,source_id=1):
	if request.user.is_authenticated:
		source=Source.objects.get(id=source_id)
		return render(request, "single_doc.html", {'source':source})
	else:
		return HttpResponseForbidden("Forbidden")

#### CONTROLLED VOCABS
	
class SourceTypeList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	These terms come from the Zotero document types; legacy values from SlaveVoyages were mapped over when the SSC project moved all the sources to Zotero.
	'''
	model=SourceTypeSerializer
	queryset=SourceType.objects.all()
	pagination_class=None
	sort_by='id'
	serializer_class=SourceTypeSerializer
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
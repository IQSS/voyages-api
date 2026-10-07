from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render,get_object_or_404
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from django.views.generic.list import ListView
from collections import Counter
import urllib
import json
import requests
import time
import collections
import gc
from voyages3.localsettings import REDIS_HOST,REDIS_PORT,DEBUG,SOLR_ENDPOINT,VOYAGES_FRONTEND_BASE_URL,OPEN_API_BASE_URL
from voyages3.settings import STATIC_ROOT
import re
import pysolr
import hashlib
from .serializers import *
from voyage.models import Voyage
from past.models import Enslaved,EnslaverIdentity
from blog.models import Post
from document.models import Source
from common.reqs import getJSONschema
import uuid
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
import redis
import os
import hashlib

redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

@extend_schema(
		exclude=True
	)
def RedisFlush(request):
	
	if request.user.is_authenticated:
		
		fa=redis_cache.flushdb()
		
		if fa:
			return HttpResponse("flushed")
		else:
			return HttpResponse("failed")
		
	else:
		return HttpResponseForbidden("Forbidden")

@extend_schema(exclude=True)
class Schemas(generics.GenericAPIView):
	def get(self,request):
		schema_name=request.GET.get('schema_name')
		hierarchical=request.GET.get('hierarchical')
		if schema_name is not None and hierarchical is not None:
			schema_json=getJSONschema(schema_name,hierarchical)
			return JsonResponse(schema_json,safe=False)
		else:
			return JsonResponse({'status':'false','message':'you must specify schema_name (string) and hierarchical (boolean)'}, status=502)		

class GlobalSearch(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint takes a string and passes it on to Solr, which searches across all indexed text fields (currently all text fields) in our core models (Voyages, Enslaved People, Enslavers, and Blog Posts [documents next...]). It returns counts and the first 10 primary keys for each",
		request=GlobalSearchRequestSerializer,
		responses=GlobalSearchResponseItemSerializer
	)
	def post(self,request):
		st=time.time()
		print("Global Search+++++++\nusername:",request.auth.user)
		
		params=dict(request.data)
		search_string=params.get('search_string')
		# Oh, yes. Little Bobby Tables, we call him.
		
		#VALIDATE THE REQUEST
		serialized_req = GlobalSearchRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		output_dict=[]
		coretuples=[
			['voyages',Voyage.objects.all()],
			['enslaved',Enslaved.objects.all()],
			['enslavers',EnslaverIdentity.objects.all()],
			['blog',Post.objects.all()],
			['sources',Source.objects.all()]
		]
		
		if search_string is None:
		
			for core in coretuples:
				corename,qset=core
				results_count=qset.count()
				topten_ids=[i[0] for i in qset[:9].values_list('id')]
				output_dict.append({
					'type':corename,
					'results_count':results_count,
					'ids':topten_ids
				})
		else:
			search_string=re.sub("\s+"," ",search_string)
			search_string=search_string.strip()
			searchstringcomponents=[''.join(filter(str.isalnum,s)) for s in search_string.split(' ')]
		
			core_names=[ct[0] for ct in coretuples]
			
			for core_name in core_names:
		
				solr = pysolr.Solr(
						f'{SOLR_ENDPOINT}/{core_name}/',
						always_commit=True,
						timeout=10
					)
				finalsearchstring="(%s)" %(" ").join(searchstringcomponents)
				results=solr.search(f'text:{finalsearchstring}')
				results_count=results.hits
				
				ids=[r['id'] for r in results]
				output_dict.append({
					'type':core_name,
					'results_count':results_count,
					'ids':ids
				})

		#VALIDATE THE RESPONSE
		serialized_resp=GlobalSearchResponseItemSerializer(data=output_dict,many=True)
		print("Internal Response Time:",time.time()-st,"\n+++++++")
		if not serialized_resp.is_valid():
			return JsonResponse(serialized_resp.errors,status=400)
		else:
			return JsonResponse(serialized_resp.data,safe=False)


class MakeSavedSearch(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint takes a filter object and specified endpoint, and returns a saved search url",
		request=MakeSavedSearchRequestSerializer,
		responses=MakeSavedSearchResponseSerializer
	)
	def post(self,request):
		
		#VALIDATE THE REQUEST
		serialized_req = MakeSavedSearchRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		srd=serialized_req.data
		
		hash_id=hashlib.sha256(json.dumps(srd,sort_keys=True,indent=1).encode('utf-8')).hexdigest()
		
		try:
			sq=SavedQuery.objects.get(hash_id=hash_id)
		except ObjectDoesNotExist:
			sq=None
		
		if sq is None:
			print("Making new saved search")
			id=None
			offset=0
			while id is None:
				try_unique_hash_id=hash_id[offset:offset+8]
				try:
					sq=SavedQuery.objects.get(id=try_unique_hash_id)
					offset+=1
				except:
					id=try_unique_hash_id
			query=serialized_req.data['query']
			endpoint=serialized_req.data['endpoint']
			front_end_path=serialized_req.data.get('front_end_path')
			SQ=SavedQuery.objects.create(
				id=id,
				hash_id=hash_id,
				endpoint=endpoint,
				query=query,
				front_end_path=front_end_path
			)
		else:
			print("retrieving existing saved search")
			id=sq.id
		
		return JsonResponse({'id':id})


class UseSavedSearch(generics.RetrieveAPIView):	
	'''
	GET a saved query by its 8-character hash id/pk
	'''
	queryset=SavedQuery.objects.all()
	serializer_class=UseSavedSearchResponseSerializer
	lookup_field="id"
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
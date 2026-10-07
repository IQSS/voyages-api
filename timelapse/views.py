import os
from django.shortcuts import render
from django.shortcuts import render,get_object_or_404
from django.http import HttpResponse, JsonResponse
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from voyages3.localsettings import REDIS_HOST,REDIS_PORT,GEO_NETWORKS_BASE_URL,STATS_BASE_URL,DEBUG,USE_REDIS_CACHE
from common.reqs import autocomplete_req,post_req,get_fieldstats,paginate_queryset,clean_long_df
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, extend_schema_view
from drf_spectacular.types import OpenApiTypes
import urllib
import json
import requests
import time
from .models import *
from .serializers import *
from rest_framework import serializers
import pprint
import redis
import hashlib
from common.static.Voyage_options import Voyage_options
from voyage.models import Nationality

redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

class VoyageAnimationGetNations(generics.GenericAPIView):
	permission_classes=[IsAuthenticated]
	authentication_classes=[TokenAuthentication]
	@extend_schema(
		description="Returns primary-keyed dictionaries of voyage nations",
		request=None,
		responses=VoyageAnimationGetNationsResponseSerializer
	)
	def get(self,request):
		st=time.time()
		print("TIMELAPSE NATIONS+++++++\nusername:",request.auth.user)
		
		if USE_REDIS_CACHE:
			hashdict={
				'req_name':"ANIMATION NATIONS",
				'req_data':None
			}
			hashed=hashlib.sha256(json.dumps(hashdict,sort_keys=True,indent=1).encode('utf-8')).hexdigest()
			cached_response = redis_cache.get(hashed)
		else:
			cached_response=None

		if cached_response is None:
			nationalities=Nationality.objects.all()
			vls=nationalities.values_list('id','name','value')
			
			resp={
				v[0]:{
					'name':v[1],
					'code':v[2]
				}
				for v in vls
			}
			
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,json.dumps(resp))
		else:
			if DEBUG:
				print("cached:",hashed)
			resp=json.loads(cached_response)
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
		return JsonResponse(resp, content_type='application/json')

class VoyageAnimationGetCompiledRoutes(generics.GenericAPIView):
	permission_classes=[IsAuthenticated]
	authentication_classes=[TokenAuthentication]
	@extend_schema(
		parameters=[
			OpenApiParameter(name='networkName',location=OpenApiParameter.QUERY, description='Network Name', required=True, type=str,enum=['trans', 'intra'],default='trans')
		],
		description="Returns primary-keyed dictionaries of ports and their regional routes for trans or intra map networks",
		request=VoyageAnimationGetCompiledRoutesRequestSerializer,
		responses=VoyageAnimationGetCompiledRoutesResponseSerializer
	)
	def get(self,request):
		st=time.time()
		print("TIMELAPSE COMPILED ROUTES+++++++\nusername:",request.auth.user)
		data=request.GET.dict()
		serialized_req = VoyageAnimationGetCompiledRoutesRequestSerializer(data=data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

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

		if cached_response is None:
			network_name = request.GET.get('networkName')
			route_type = request.GET.get('routeType')
			ports_fpath = os.path.join(settings.STATIC_ROOT, "legacy_timelapse", network_name, "port_routes.json")
			routes_fpath = os.path.join(settings.STATIC_ROOT, "legacy_timelapse", network_name, "regional_routes.json")
			ports_f=open(ports_fpath, 'rb')
			routes_f=open(routes_fpath,'rb')
			
			ports=json.loads(ports_f.read())
			routes=json.loads(routes_f.read())
			
			resp={
				"ports":ports,
				"routes":routes
			}
			
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,json.dumps(resp))
		else:
			if DEBUG:
				print("cached:",hashed)
			resp=json.loads(cached_response)
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
		
		return JsonResponse(resp, content_type='application/json')

class VoyageAnimation(generics.GenericAPIView):
	permission_classes=[IsAuthenticated]
	authentication_classes=[TokenAuthentication]
	@extend_schema(
		description="Port-over for the legacy timelapse feature. To be replaced in 2024.",
		request=TimeLapaseRequestSerializer,
		responses=TimeLapseResponseItemSerializer
	)
	def post(self,request):	
		st=time.time()
		print("TIMELAPSE+++++++\nusername:",request.auth.user)
		#VALIDATE THE REQUEST
		serialized_req = TimeLapaseRequestSerializer(data=request.data)
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
			queryset=Voyage.objects.all()
			print("BEFORE---->",queryset.count())
			
			queryset,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=True
			)
						
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
			
			print("AFTER---->",results_count,queryset.count())
			#MAKE THE CROSSTABS REQUEST TO VOYAGES-STATS
			ids=[i[0] for i in queryset.values_list('id')]
			u2=STATS_BASE_URL+'timelapse/'
			params=dict(request.data)
			stats_req_data=params
			stats_req_data['ids']=ids
			stats_req_data['cachename']='timelapse'
			r=requests.post(url=u2,data=json.dumps(stats_req_data),headers={"Content-type":"application/json"})
			
			#VALIDATE THE RESPONSE
			if r.ok:
				j=json.loads(r.text)
				print(j[0])
				serialized_resp=TimeLapseResponseItemSerializer(data=j,many=True)
			if not serialized_resp.is_valid():
				return JsonResponse(serialized_resp.errors,status=500,safe=False)
			else:
				resp=serialized_resp.data
			#SAVE THIS NEW RESPONSE TO THE REDIS CACHE
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,json.dumps(resp))			
		else:
			if DEBUG:
				print("cached:",hashed)
			resp=json.loads(cached_response)
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
		
		return JsonResponse(resp,safe=False,status=200)
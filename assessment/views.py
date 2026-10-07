from django.shortcuts import render
from django.db.models import Q,Prefetch
from django.http import HttpResponse, JsonResponse
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from django.views.generic.list import ListView
import urllib
import json
import requests
import time
from .models import *
from .serializers import *
import pprint
from common.reqs import *
import collections
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from common.static.Estimate_options import Estimate_options
from voyages3.localsettings import STATS_BASE_URL,GEO_NETWORKS_BASE_URL,DEBUG,USE_REDIS_CACHE,REDIS_HOST,REDIS_PORT
import redis
import hashlib

redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

#list view. Only keeping it around for swagger to have access to the model
class AssessmentList(generics.RetrieveAPIView):	
	queryset=Estimate.objects.all()
	lookup_field='id'
	serializer_class=EstimateSerializer
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]

class EstimateDataFrames(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The dataframes endpoint is mostly for internal use -- building up caches of data in the flask services.\n\
		However, it could be used for csv exports and the like.\n\
		Be careful! It's a resource hog.",
		request=EstimateDataframesRequestSerializer
	)
	def post(self,request):
		print("ESTIMATE DATAFRAMES+++++++\nusername:",request.auth.user)
		st=time.time()
		
		#VALIDATE THE REQUEST
		serialized_req = EstimateDataframesRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
		queryset=Estimate.objects.all()
# 		print(queryset)
		results,results_count,page,page_size,error_messages=post_req(
			queryset,
			self,
			request,
			Estimate_options,
			auto_prefetch=True
		)
		
		results=results.order_by('id')
		sf=request.data.get('selected_fields')
		output_dicts={}
		vals=list(eval('queryset.values_list("'+'","'.join(sf)+'")'))
		
		for i in range(len(sf)):
			output_dicts[sf[i]]=[v[i] for v in vals]
		print("Internal Response Time:",time.time()-st,"\n+++++++")
		
		## DIFFICULT TO VALIDATE THIS WITH A SERIALIZER -- NUMBER OF KEYS AND DATATYPES WITHIN THEM CHANGES DYNAMICALLY ACCORDING TO REQ
		
		return JsonResponse(output_dicts,safe=False)

class EstimateTimeline(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="Paginated crosstabs endpoint, with Pandas as the back-end.",
		request=EstimateTimelineRequestSerializer,
		responses=EstimateTimeLineResponseItemSerializer
	)
	def post(self,request):
		st=time.time()
		print("ESTIMATE TIMELINE+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = EstimateTimelineRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
		queryset=Estimate.objects.all()
		results,results_count,page,page_size,error_messages=post_req(
			queryset,
			self,
			request,
			Estimate_options,
			auto_prefetch=True
		)
		
		if error_messages:
			return(JsonResponse(error_messages,safe=False,status=400))

		
		#MAKE THE CROSSTABS REQUEST TO VOYAGES-STATS
		ids=[i[0] for i in results.values_list('id')]
		u2=STATS_BASE_URL+'estimates_timeline/'
		params=dict(request.data)
		stats_req_data=params
		stats_req_data['ids']=ids
		r=requests.post(url=u2,data=json.dumps(stats_req_data),headers={"Content-type":"application/json"})
		
		#VALIDATE THE RESPONSE
		if r.ok:
			j=json.loads(r.text)
			
			#legacy format
			transformed_j=[]
			
# 			try:
			jvars=[
				['disembarked_slaves','y0'],
				['embarked_slaves','y1'],
				['year','x']
			]
			for i in range(len(j[jvars[0][0]])):
				item={}
				for k in jvars:
					val=j[k[0]][i]
					item[k[1]]=val
				transformed_j.append(item)
			
			serialized_resp=EstimateTimeLineResponseItemSerializer(data=transformed_j,many=True)
# 			except:
# 			return JsonResponse(status=500)
			
		print("Internal Response Time:",time.time()-st,"\n+++++++")
		if not serialized_resp.is_valid():
			return JsonResponse(serialized_resp.errors,status=400)
		else:
			return JsonResponse(serialized_resp.data,safe=False)

class EstimateCrossTabs(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="HTML dump crosstabs endpoint, with Pandas as the back-end.",
		request=EstimateCrossTabRequestSerializer,
		responses=EstimateCrossTabResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("ESTIMATE CROSSTABS+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = EstimateCrossTabRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
		queryset=Estimate.objects.all()
		results,results_count,page,page_size,error_messages=post_req(
			queryset,
			self,
			request,
			Estimate_options,
			auto_prefetch=True,
			paginate=False
		)
		
		if error_messages:
			return(JsonResponse(error_messages,safe=False,status=400))
		
		#MAKE THE CROSSTABS REQUEST TO VOYAGES-STATS
		ids=[i[0] for i in results.values_list('id')]
		print(f"NUMBER OF IDS: {len(ids)}")
		u2=STATS_BASE_URL+'estimates_pivot/'
		params=dict(request.data)
		stats_req_data=params
		stats_req_data['ids']=ids
		r=requests.post(url=u2,data=json.dumps(stats_req_data),headers={"Content-type":"application/json"})
		
		#VALIDATE THE RESPONSE
		if r.ok:
			j=json.loads(r.text)
			serialized_resp=EstimateCrossTabResponseSerializer(data=j)
		print("Internal Response Time:",time.time()-st,"\n+++++++")
		
		#WE NEED TO SEND BACK THE RESPONSE AS A CSV, PROBABLY USING THIS: django.http.response.FileResponse
		
		if not serialized_resp.is_valid():
			return JsonResponse(serialized_resp.errors,status=400)
		else:
			return JsonResponse(serialized_resp.data,safe=False)

class EstimateAggRoutes(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint provides a collection of multi-valued weighted nodes and splined, weighted edges. The intended use-case is the drawing of a geographic sankey map.",
		request=EstimateAggRoutesRequestSerializer,
		responses=EstimateAggRoutesResponseSerializer,
	)
	def post(self,request):
		st=time.time()
		if DEBUG:
			print("ESTIMATES AGGREGATION ROUTES+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = EstimateAggRoutesRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
# 		
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
			#FILTER THE Estimates BASED ON THE REQUEST'S FILTER OBJECT
			params=dict(request.data)
			queryset=Estimate.objects.all()
			zoomlevel=params.get('zoomlevel','region')
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Estimate_options,
				auto_prefetch=True
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

		
			#HAND OFF TO THE FLASK CONTAINER
			results=results.order_by('id')
			values_list=results.values_list('id')
			pks=[v[0] for v in values_list]
			django_query_time=time.time()
			print("Internal Django Response Time:",django_query_time-st,"\n+++++++")
			u2=GEO_NETWORKS_BASE_URL+'network_maps/'
			d2={
				'graphname':zoomlevel,
				'cachename':'estimate_maps',
				'pks':pks
			}
			r=requests.post(url=u2,data=json.dumps(d2),headers={"Content-type":"application/json"})
	# 			#VALIDATE THE RESPONSE
			if r.ok:
				j=json.loads(r.text)
				serialized_resp=EstimateAggRoutesResponseSerializer(data=j)
			if not serialized_resp.is_valid():
				return JsonResponse(serialized_resp.errors,status=400)
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
# 		print(resp)
		return JsonResponse(resp,safe=False,status=200)
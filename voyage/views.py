from django.shortcuts import render,get_object_or_404
from django.http import HttpResponse, JsonResponse
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from django.views.generic.list import ListView
from rest_framework.pagination import PageNumberPagination
from collections import Counter
import urllib
import json
import requests
import time
from .models import *
import pprint
import redis
import hashlib
from rest_framework import filters
from common.reqs import autocomplete_req,post_req,get_fieldstats,paginate_queryset,clean_long_df,use_redis
from geo.common import GeoTreeFilter
from geo.serializers import LocationSerializerDeep
import collections
import gc
from .serializers import *
from rest_framework import serializers
from voyages3.localsettings import REDIS_HOST,REDIS_PORT,GEO_NETWORKS_BASE_URL,STATS_BASE_URL,DEBUG,USE_REDIS_CACHE
import re
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, extend_schema_view
from drf_spectacular.types import OpenApiTypes
from common.static.Voyage_options import Voyage_options
import pickle
from voyage.cross_filter_fields import VoyageBasicFilterVarNames

redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

class VoyageList(generics.GenericAPIView):
	permission_classes=[IsAuthenticated]
	authentication_classes=[TokenAuthentication]
	@extend_schema(
		description="This endpoint returns a list of nested objects, each of which contains all the available information on individual voyages.\n\
		\Voyages are the legacy natural unit of the project. They are useful because they gather together:\n\
		\n\
			1. Numbers of people and demographic data\n\
			2. Geographic itinerary data\n\
			3. Important dates\n\
			4. Named individuals\n\
			5. Documentary sources\n\
			6. Data on the vessel\
		\n\
		\nYou can filter on any field by 1) using double-underscore notation to concatenate nested field names and 2) conforming your filter to request parser rules for numeric, short text, global search, and geographic types.\
		",
		request=VoyageListRequestSerializer,
		responses=VoyageListResponseSerializer
	)
	def post(self,request):	
		st=time.time()
		print("VOYAGE LIST+++++++\nusername:",request.auth.user)
		#VALIDATE THE REQUEST
		serialized_req = VoyageListRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)
		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=True,
				paginate=True
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			resp=VoyageListResponseSerializer({
				'count':results_count,
				'page':page,
				'page_size':page_size,
				'results':results
			}).data
			#I'm having the most difficult time in the world validating this nested paginated response
			#And I cannot quite figure out how to just use the built-in paginator without moving to urlparams
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

#You don't want to see this thing on swagger -- it'll crash the browser.
# @extend_schema(exclude=True)
class VoyageDownload(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="Users like downloading csv's. We have to have split fields in here for things like enslaver names/roles",
		request=VoyageDownloadRequestSerializer
	)
	def post(self,request):
		print("VOYAGE FLAT DOWNLOADS+++++++\nusername:",request.auth.user)
		st=time.time()
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageDownloadRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		
		hashed,cached_response=use_redis(serialized_req,self)
				
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=True,
				paginate=False
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
			
			ids=[i[0] for i in results.values_list('id')]
			
			u2=STATS_BASE_URL+'csv_download/'
			params=dict(request.data)
			stats_req_data=params
			stats_req_data['ids']=ids
			stats_req_data['cachename']='big_df'
			r=requests.post(url=u2,data=json.dumps(stats_req_data),headers={"Content-type":"application/json"})
			
			#VALIDATE THE RESPONSE
			if r.ok:
				resp=r.content
			else:
				return JsonResponse({"message":"unknown error"},status=400)
			
			#SAVE THIS NEW RESPONSE TO THE REDIS CACHE
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,resp)

		else:
			if DEBUG:
				print("cached:",hashed)
			resp=cached_response
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
		
		return HttpResponse(resp, content_type='application/octet-stream',status=200)

class VoyageAggregations(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The aggregations endpoints helps us to peek at numerical fields in the same way that autcomplete endpoints help us to get a sense of what the available text values are on a field.\
		So if we want to, for instance, allow a user to search on voyages by year, we might want to give them a rangeslider component. In order to make that rangeslider component, you'd have to know the minimum and maximum years during which voyages sailed -- you would also need to know, of course, whether you were searching for the minimum and maximum of years of departure, embarkation, disembarkation, return, etc.\
		Also, as with the other new endpoints we are rolling out in January 2024, you can run a filter before you query for min/max on variables. So if you've already searched for voyages arriving in Cuba, for instance, you can ask for the min and max years of disembarkation in order to make a rangeslider dynamically tailored to that search.\
		Note to maintainer(s): This endpoint was made with rangesliders in mind, so we are only exposing min & max for now. In the future, it could be very useful to have median, mean, or plug into the stats engine for a line or bar chart to create some highly interactive filtering.\
		",
		request=VoyageFieldAggregationRequestSerializer,
		responses=VoyageFieldAggregationResponseSerializer
	)
	def post(self,request):
		st=time.time()
		if DEBUG:
			print("VOYAGE AGGREGATIONS+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageFieldAggregationRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)
		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			
			#clean the request
			reqdict=dict(serialized_req.data)
			var_name=reqdict.get('varName')
			filteritems=reqdict.get('filter')
			cleanedfilteritems=[]
			if filteritems is not None:
				for filteritem in filteritems:
					if var_name!=filteritem['varName']:
						cleanedfilteritems.append(filteritem)
			reqdict['filter']=cleanedfilteritems
			
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				reqdict,
				Voyage_options,
				auto_prefetch=False
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			#RUN THE AGGREGATIONS
			aggregation_field=request.data.get('varName')
			output_dict,errormessages=get_fieldstats(results,aggregation_field,Voyage_options)
			#VALIDATE THE RESPONSE
			serialized_resp=VoyageFieldAggregationResponseSerializer(data=output_dict)
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
		
		return JsonResponse(resp,safe=False,status=200)

class VoyageCrossTabs(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="Paginated crosstabs endpoint, with Pandas as the back-end.",
		request=VoyageCrossTabRequestSerializer,
		responses=VoyageCrossTabResponseSerializer
	)
	def post(self,request):
		st=time.time()
		if DEBUG:
			print("VOYAGE CROSSTABS+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageCrossTabRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)
		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=True
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

		
			#MAKE THE CROSSTABS REQUEST TO VOYAGES-STATS
			ids=[i[0] for i in results.values_list('id')]
			u2=STATS_BASE_URL+'crosstabs/'
			params=dict(request.data)
			stats_req_data=params
			stats_req_data['ids']=ids
			stats_req_data['cachename']='voyage_pivot_tables'
			r=requests.post(url=u2,data=json.dumps(stats_req_data),headers={"Content-type":"application/json"})
			print(r)
			#VALIDATE THE RESPONSE
			if r.ok:
				j=json.loads(r.text)
				serialized_resp=VoyageCrossTabResponseSerializer(data=j)
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
		
		return JsonResponse(resp,safe=False,status=200)




class VoyageLineAndBarCharts(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint is for building line and bar charts. It requires a few arguments, which it basically inherits from pandas.\n\
		    1. A variable to group on: 'by'\n\
		    2. A numeric variable to aggregate: 'vals'\n\
		    3. An aggregation function: sum, mean, min, max, count\n\
		It returns a dictionary whose keys are the supplied variable names, and whose values are equal-length arrays -- in essence, a long dataframe.\n\
		",
		request=VoyageLineAndBarChartsRequestSerializer,
	)

	def post(self,request):
		st=time.time()
		if DEBUG:
			print("VOYAGE LINEANDBARCHART+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageLineAndBarChartsRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)
		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=False
			)

			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			#EXTRACT THE VOYAGE IDS AND HAND OFF TO THE STATS FLASK CONTAINER
			ids=[i[0] for i in results.values_list('id')]
			u2=STATS_BASE_URL+'groupby/'
			rdata=dict(request.data)
			groupby=rdata.get('groupby')
			by=groupby['by']
			
			resp={}
			for a_s in groupby['agg_series']:
				agg_fn=a_s['agg_fn']
				vals=a_s['vals']
				d2={
					'by':groupby['by'],
					'vals':vals, #the stats engine needs this string to be an array
					'ids':ids,
					'agg_fn':a_s['agg_fn']
				}
				by=re.sub("__bins__[0-9]+","",by)
				json_resp=requests.post(url=u2,data=json.dumps(d2),headers={"Content-type":"application/json"})
				pandas_resp=json.loads(json_resp.text)
				resp[by]=pandas_resp[by]
				resp[f'{vals}__{agg_fn}']=pandas_resp[vals]
			
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

class VoyagePieCharts(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint is for building pie charts. It requires a few arguments, which it basically inherits from pandas.\n\
		    1. A categorical variable to group on: 'by'\n\
		    2. A numeric variable to aggregate: 'vals'\n\
		    3. An aggregation function: sum, mean, min, max, count\n\
		It returns a dictionary whose keys are the supplied variable names, and whose values are equal-length arrays -- in essence, a long dataframe.\n\
		",
		request=VoyagePieChartRequestSerializer,
	)

	def post(self,request):
		st=time.time()
		if DEBUG:
			print("VOYAGE PIECHART+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = VoyagePieChartRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)
		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=False
			)

			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			#EXTRACT THE VOYAGE IDS AND HAND OFF TO THE STATS FLASK CONTAINER
			ids=[i[0] for i in results.values_list('id')]
			u2=STATS_BASE_URL+'groupby/'
			rdata=dict(request.data)
			groupby=rdata.get('groupby')
			d2=dict(groupby)
			d2['ids']=ids
		
			#NOT QUITE SURE HOW TO VALIDATE THE RESPONSE OF THIS VIA A SERIALIZER
			json_resp=requests.post(url=u2,data=json.dumps(d2),headers={"Content-type":"application/json"})
			resp=json.loads(json_resp.text)
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

class VoyageSummaryStats(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="A summary statistics table. Minimal but customized.",
		request=VoyageSummaryStatsRequestSerializer,
		responses=VoyageSummaryStatsResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("VOYAGE SUMMARY STATS+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageSummaryStatsRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
		queryset=Voyage.objects.all()
		results,results_count,page,page_size,error_messages=post_req(
			queryset,
			self,
			request,
			Voyage_options,
			auto_prefetch=True
		)

		if error_messages:
			return(JsonResponse(error_messages,safe=False,status=400))

		#MAKE THE CROSSTABS REQUEST TO VOYAGES-STATS
		ids=[i[0] for i in results.values_list('id')]
		u2=STATS_BASE_URL+'voyage_summary_stats/'
		params=dict(request.data)
		stats_req_data=params
		stats_req_data['ids']=ids
		r=requests.post(url=u2,data=json.dumps(stats_req_data),headers={"Content-type":"application/json"})
		print(r)
		#VALIDATE THE RESPONSE
		if r.ok:
			j=json.loads(r.text)
			serialized_resp=VoyageSummaryStatsResponseSerializer(data=j)
		print("Internal Response Time:",time.time()-st,"\n+++++++")
		if not serialized_resp.is_valid():
			return JsonResponse(serialized_resp.errors,status=400)
		else:
			return JsonResponse(serialized_resp.data,safe=False)

class VoyageDataFrames(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The dataframes endpoint is mostly for internal use -- building up caches of data in the flask services.\n\
		However, it could be used for csv exports and the like.\n\
		Be careful! It's a resource hog. But more importantly, if you request fields that are not one-to-one relationships with the voyage, you're likely get back extra rows. For instance, requesting captain names will return one row for each captain, not for each voyage.\n\
		And finally, the example provided below puts a strict year filter on because unrestricted, it will break your swagger viewer :) \n\
		",
		request=VoyageDataframesRequestSerializer,
# 		responses=VoyageDataframesResponseSerializer
	)
	def post(self,request):
		print("VOYAGE DATAFRAMES+++++++\nusername:",request.auth.user)
		st=time.time()
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageDataframesRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)

		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=True,
				paginate=False
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
		
			results=results.order_by('id')
			sf=request.data.get('selected_fields')
			vals=list(eval('results.values_list("'+'","'.join(sf)+'")'))
			resp=clean_long_df(vals,sf)		
			## DIFFICULT TO VALIDATE THIS WITH A SERIALIZER -- NUMBER OF KEYS AND DATATYPES WITHIN THEM CHANGES DYNAMICALLY ACCORDING TO REQ
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

class VoyageGeoTreeFilter(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint is tricky. In addition to taking a filter object, it also takes a list of geographic value variable names, like 'voyage_itinerary__port_of_departure__value'. \n\
		What it returns is a hierarchical tree of SlaveVoyages geographic data, filtered down to only the values used in those 'geotree valuefields' after applying the filter object.\n\
		So if you were to ask for voyage_itinerary__port_of_departure__value, you would mostly get locations in Europe and the Americas; and if you searched 'voyage_itinerary__imp_principal_region_of_slave_purchase__name', you would principally get places in the Americas and Africa.",
		request=VoyageGeoTreeFilterRequestSerializer,
		responses=LocationSerializerDeep
	)
	def post(self,request):
		st=time.time()
		print("VOYAGE GEO TREE FILTER+++++++\nusername:",request.auth.user)
		#CLEAN THE REQUEST'S FILTER (IF ANY)
		reqdict=dict(request.data)
		if 'filter' in reqdict:		
			for filteritem in list(reqdict['filter']):
				if filteritem['varName'] not in VoyageBasicFilterVarNames:
					reqdict['filter'].remove(filteritem)
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageGeoTreeFilterRequestSerializer(data=reqdict)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)

		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:		
			#extract and then peel out the geotree_valuefields
			geotree_valuefields=reqdict['geotree_valuefields']
			del(reqdict['geotree_valuefields'])
		
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				reqdict,
				Voyage_options
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
		
			#THEN GET THE CORRESPONDING GEO VALUES
			for geotree_valuefield in geotree_valuefields:
				geotree_valuefield_stub='__'.join(geotree_valuefield.split('__')[:-1])
				results=results.select_related(geotree_valuefield_stub)
			
			vls=[]
			
			for geotree_valuefield in geotree_valuefields:		
				vls+=[i[0] for i in list(set(results.values_list(geotree_valuefield))) if i[0] is not None]
			vls=list(set(vls))
		
			#THEN GET THE GEO OBJECTS BASED ON THAT OPERATION
			resp=GeoTreeFilter(spss_vals=vls)
		
			### CAN'T FIGURE OUT HOW TO SERIALIZE THIS...
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

class VoyageAggRoutes(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint provides a collection of multi-valued weighted nodes and splined, weighted edges. The intended use-case is the drawing of a geographic sankey map.",
		request=VoyageAggRoutesRequestSerializer,
		responses=VoyageAggRoutesResponseSerializer,
	)
	def post(self,request):
		st=time.time()
		if DEBUG:
			print("VOYAGE AGGREGATION ROUTES+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = VoyageAggRoutesRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)
		
		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		hashed,cached_response=use_redis(serialized_req,self)

		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE VOYAGES BASED ON THE REQUEST'S FILTER OBJECT
			params=dict(request.data)
			queryset=Voyage.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Voyage_options,
				auto_prefetch=True
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
		
			#HAND OFF TO THE FLASK CONTAINER
			results=results.order_by('id')
			zoomlevel=params.get('zoomlevel','region')
			values_list=results.values_list('id')
			pks=[v[0] for v in values_list]
			django_query_time=time.time()
			print("Internal Django Response Time:",django_query_time-st,"\n+++++++")
			u2=GEO_NETWORKS_BASE_URL+'network_maps/'
			d2={
				'graphname':zoomlevel,
				'cachename':'voyage_maps',
				'pks':pks
			}
			r=requests.post(url=u2,data=json.dumps(d2),headers={"Content-type":"application/json"})

			#VALIDATE THE RESPONSE
			if r.ok:
				j=json.loads(r.text)
				serialized_resp=VoyageAggRoutesResponseSerializer(data=j)
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
		
		return JsonResponse(resp,safe=False,status=200)

######## CRUD ENDPOINTS

class VoyageGET(generics.RetrieveAPIView):
	'''
	GET one voyage by its ID (for card view)
	'''
	queryset=Voyage.objects.all()
	serializer_class=VoyageSerializer
	lookup_field='voyage_id'

class CargoTypeList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=CargoType
	queryset=CargoType.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=CargoTypeSerializer

class AfricanInfoList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=AfricanInfo
	queryset=AfricanInfo.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=AfricanInfoSerializer

class RigOfVesselList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=RigOfVessel
	queryset=RigOfVessel.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=RigOfVesselSerializer

class NationalityList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=NationalitySerializer
	queryset=Nationality.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=NationalitySerializer

class TonTypeList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=TonTypeSerializer
	queryset=TonType.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=TonTypeSerializer
	
class ParticularOutcomeList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=ParticularOutcomeSerializer
	queryset=ParticularOutcome.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=ParticularOutcomeSerializer

class SlavesOutcomeList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=SlavesOutcomeSerializer
	queryset=SlavesOutcome.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=SlavesOutcomeSerializer

class ResistanceList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=Resistance
	queryset=Resistance.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=ResistanceSerializer
	
class OwnerOutcomeList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=OwnerOutcomeSerializer
	queryset=OwnerOutcome.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=OwnerOutcomeSerializer

class VesselCapturedOutcomeList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	+++ Need a write-up from the team on the meaning of this variable.
	'''
	model=VesselCapturedOutcomeSerializer
	queryset=VesselCapturedOutcome.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=VesselCapturedOutcomeSerializer
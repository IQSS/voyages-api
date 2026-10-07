from django.shortcuts import render
from django.db.models import Q,Prefetch
from django.http import HttpResponse, JsonResponse
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from django.views.generic.list import ListView
from django.views.generic.base import TemplateView
import urllib
import json
import requests
import time
from .models import *
from .serializers import *
import redis
import hashlib
import pprint
from common.reqs import autocomplete_req,post_req,get_fieldstats,paginate_queryset,clean_long_df
from collections import Counter
from geo.common import GeoTreeFilter
from geo.serializers import LocationSerializer,LocationSerializerDeep
from voyages3.localsettings import REDIS_HOST,REDIS_PORT,DEBUG,GEO_NETWORKS_BASE_URL,PEOPLE_NETWORKS_BASE_URL,USE_REDIS_CACHE
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from common.static.EnslaverIdentity_options import EnslaverIdentity_options
from common.static.Enslaved_options import Enslaved_options
from common.static.EnslavementRelation_options import EnslavementRelation_options
from common.serializers import autocompleterequestserializer, autocompleteresponseserializer
from past.cross_filter_fields import EnslaverBasicFilterVarNames,EnslavedBasicFilterVarNames
from django.core.management import call_command


redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

class EnslavedList(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint returns a list of highly nested objects, each of which contains all the available information on enslaved individuals who we know to have been transported on a voyage.\
		This people-oriented data dramatically changes the nature of our dataset. While Voyages data has always been relational, the complexity of interpersonal connections in this dataset makes it graph-like and pushes the boundaries of the underlying system (Python Django).\
		For instance, you might search for a person who was bought, sold, or transported on a voyage owned by a known enslaver. Or, you might search for people who, based on the sound of their name as recorded, are believed to have come from a particular region in Africa where an ethnic group known to use that name was located.\
		However, it must be stressed that there is a tension in this dataset: the data that we have on enslaved individuals was almost entirely recorded by the people who enslaved them, or by colonial managers who technically liberated them, but oftentimes pressed these people into military service or labor. We know the names of these people, which is grounbreaking for this project because it allows us to identify named individuals in a dataset that often records only nameless quantities of people, but as you analyze this dataset you will note that most of the data we have on these enslaved people is bio-data, such as gender, age, height, and skin color -- this is qualitatively different than the data we have on the enslavers, about whom we often have a good deal of biographical data.\
		You can filter on any field by 1) using double-underscore notation to concatenate nested field names and 2) conforming your filter to request parser rules for numeric, short text, global search, and geographic types.",
		request=EnslavedListRequestSerializer,
		responses=EnslavedListResponseSerializer
	)
	def post(self,request):
		
		st=time.time()
		print("ENSLAVED LIST+++++++\nusername:",request.auth.user)
		st2=time.time()
		#VALIDATE THE REQUEST
		serialized_req = EnslavedListRequestSerializer(data=request.data)
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
		if DEBUG:
			print(f'PREFLIGHT AND REDIS TIME: {time.time()-st2}')
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			st3=time.time()
			#FILTER THE ENSLAVED PEOPLE ENTRIES BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Enslaved.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Enslaved_options,
				auto_prefetch=True,
				paginate=True
			)
						
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
			
			if DEBUG:
				print(f'QUERYSET TIME: {time.time()-st3}')
			st5=time.time()
			resp=EnslavedListResponseSerializer({
				'count':results_count,
				'page':page,
				'page_size':page_size,
				'results':results
			}).data
			if DEBUG:
				print(f'SERIALIZATION TIME: {time.time()-st5}')
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
		
class EnslavedCharFieldAutoComplete(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The autocomplete endpoints provide paginated lists of values on fields related to the endpoints primary entity (here, enslaved people). It also accepts filters. This means that you can apply any filter you would to any other query, for instance, the enslavers list view, in the process of requesting your autocomplete suggestions, thereby rapidly narrowing your search.",
		request=EnslavedAutoCompleteRequestSerializer,
		responses=EnslavedAutoCompleteResponseSerializer,
	)	
	def post(self,request):
		st=time.time()
		print("ENSLAVED CHAR FIELD AUTOCOMPLETE+++++++\nusername:",request.auth.user)
		#CLEAN THE REQUEST'S FILTER (IF ANY)
		reqdict=dict(request.data)
		if 'filter' in reqdict:		
			for filteritem in list(reqdict['filter']):
				if filteritem['varName'] not in EnslavedBasicFilterVarNames:
					reqdict['filter'].remove(filteritem)

		#VALIDATE THE REQUEST
		serialized_req = EnslavedAutoCompleteRequestSerializer(data=reqdict)
		
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
		
		if cached_response is None:
			#FILTER THE ENSLAVED PEOPLE BASED ON THE REQUEST'S FILTER OBJECT
			unfiltered_queryset=Enslaved.objects.all()
			#RUN THE AUTOCOMPLETE ALGORITHM
			final_vals=autocomplete_req(unfiltered_queryset,self,reqdict,Enslaved_options,'Enslaved')
			resp=reqdict
			resp['suggested_values']=final_vals
			#VALIDATE THE RESPONSE
			serialized_resp=EnslavedAutoCompleteResponseSerializer(data=resp)
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

class EnslavedLanguageGroupTree(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="For African Origins. A two-level tree of Modern African Countries with the child items being the African languages that were historically located within the current bounds of those countries. Language groups that are associated with more than one country are grouped under the artificial key 'Multi-Country', which is not in the database.",
		request=serializers.JSONField(),
		responses=serializers.JSONField(),
	)
	def post(self,request):
		st=time.time()
		print("LANGUAGE GROUP TREE (#NOFILTER)+++++++\nusername:",request.auth.user)
		serialized_req = EnslaverAutoCompleteRequestSerializer(data=request.data)
		elgs=LanguageGroup.objects.all()
		elgt={
			0: {
				"name":"Multi-Country",
				"id":0,
				"children":[]
			}
		}
		for elg in elgs:
			lg_dict={'id':elg.id,'name':elg.name}
			mc_set=elg.moderncountry_set.all()
			mc_id=None
			if len(mc_set)>1:
				mc_name="Multi-Country"
				mc_id=0
				elgt[0]['children'].append(lg_dict)
			elif len(mc_set)==1:
				mc_name=mc_set[0].name
				mc_id=mc_set[0].id
				
				if mc_id in elgt:
					elgt[mc_id]['children'].append(lg_dict)
				else:
					elgt[mc_id]={
						"name":mc_name,
						"id":mc_id,
						"children": [lg_dict]
					}
		resp=[elgt[v] for v in elgt]
		return JsonResponse(resp,safe=False,status=200)

@extend_schema(
		exclude=True
	)
def IndexEnslaverData(request):
	if request.user.is_authenticated:
		call_command('index_enslaver_data')
		return("didn't crash")
	else:
		return HttpResponseForbidden("Forbidden")

class EnslaverList(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint returns a list of highly nested objects, each of which contains all the available information on named individuals we know to have participated in the slave trade.\
		This people-oriented data dramatically changes the nature of our dataset. While Voyages data has always been relational, the complexity of interpersonal connections in this dataset makes it graph-like and pushes the boundaries of the underlying system (Python Django).\
		Before 2022, the project had only recorded ship captains and ship owners. We now have a much more robust accounting of individuals, sometimes recorded under different names, participating in multiple voyages, and operating in a range of different roles, from investors to brokers to buyers and sellers of enslaved people. In some cases, we know the names of these enslavers' spouses, and the amounts of money they willed to their descendants upon their death. We are very much looking forward to linking this network of enslavers into other public datasets such as Stanford's Kindred network in order to map the economic legacy of these ill-gotten gains\
		You can filter on any field by 1) using double-underscore notation to concatenate nested field names and 2) conforming your filter to request parser rules for numeric, short text, global search, and geographic types.",
		request=EnslaverListRequestSerializer,
		responses=EnslaverListResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("ENSLAVER LIST+++++++\nusername:",request.auth.user)

		#VALIDATE THE REQUEST
		serialized_req = EnslaverListRequestSerializer(data=request.data)
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
			#FILTER THE ENSLAVERS BASED ON THE REQUEST'S FILTER OBJECT
			queryset=EnslaverIdentity.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				EnslaverIdentity_options,
				auto_prefetch=True,
				paginate=True
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			resp=EnslaverListResponseSerializer({
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

class EnslavedAggregations(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The aggregations endpoints helps us to peek at numerical fields in the same way that autcomplete endpoints help us to get a sense of what the available text values are on a field.\
		So if we want to, for instance, allow a user to search on voyages by year, we might want to give them a rangeslider component. In order to make that rangeslider component, you'd have to know the minimum and maximum years during which voyages sailed -- you would also need to know, of course, whether you were searching for the minimum and maximum of years of departure, embarkation, disembarkation, return, etc.\
		Also, as with the other new endpoints we are rolling out in January 2024, you can run a filter before you query for min/max on variables. So if you've already searched for voyages arriving in Cuba, for instance, you can ask for the min and max years of disembarkation in order to make a rangeslider dynamically tailored to that search.\
		Note to maintainer(s): This endpoint was made with rangesliders in mind, so we are only exposing min & max for now. In the future, it could be very useful to have median, mean, or plug into the stats engine for a line or bar chart to create some highly interactive filtering.\
		",
		request=EnslavedFieldAggregationRequestSerializer,
		responses=EnslavedFieldAggregationResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("ENSLAVED AGGREGATIONS+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = EnslavedFieldAggregationRequestSerializer(data=request.data)
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
			queryset=Enslaved.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Enslaved_options,
				auto_prefetch=False,
				paginate=False
			)

			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
		
			#RUN THE AGGREGATIONS
			aggregation_field=request.data.get('varName')
			output_dict,errormessages=get_fieldstats(results,aggregation_field,Enslaved_options)
			#VALIDATE THE RESPONSE
			serialized_resp=EnslavedFieldAggregationResponseSerializer(data=output_dict)
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

class EnslaverAggregations(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The aggregations endpoints helps us to peek at numerical fields in the same way that autcomplete endpoints help us to get a sense of what the available text values are on a field.\
		So if we want to, for instance, allow a user to search enslavers by the year that the voyages they were associated with operated, then we might want to give them a rangeslider component. In order to make that rangeslider component, you'd have to know the minimum and maximum years during which voyages sailed -- you would also need to know, of course, whether you were searching for the minimum and maximum of years of departure, embarkation, disembarkation, return, etc.\
		Also, as with the other new endpoints we are rolling out in January 2024, you can run a filter before you query for min/max on variables. So if you've already searched for enslavers associated with voyages arriving in Cuba, for instance, you can ask for the min and max years of disembarkation in order to make a rangeslider dynamically tailored to that search.\
		Note to maintainer(s): This endpoint was made with rangesliders in mind, so we are only exposing min & max for now. In the future, it could be very useful to have median, mean, or plug into the stats engine for a line or bar chart to create some highly interactive filtering.\
		",
		request=EnslaverFieldAggregationRequestSerializer,
		responses=EnslaverFieldAggregationResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("ENSLAVER AGGREGATIONS+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		print(request.data)
		serialized_req = EnslaverFieldAggregationRequestSerializer(data=request.data)
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
			queryset=EnslaverIdentity.objects.all()
			
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
				request,
				EnslaverIdentity_options,
				auto_prefetch=False,
				paginate=False
			)
			
			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
		
			#RUN THE AGGREGATIONS
			aggregation_field=request.data.get('varName')
			output_dict,errormessages=get_fieldstats(results,aggregation_field,EnslaverIdentity_options)
		
			#VALIDATE THE RESPONSE
			serialized_resp=EnslaverFieldAggregationResponseSerializer(data=output_dict)
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

class EnslavedDataFrames(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The dataframes endpoint is mostly for internal use -- building up caches of data in the flask services.\n\
		However, it could be used for csv exports and the like.\n\
		Be careful! It's a resource hog. But more importantly, if you request fields that are not one-to-one relationships with the voyage, you're likely get back extra rows.\n\
		And finally, the example provided below puts a strict year filter on because unrestricted, it will break your swagger viewer :) \n\
		",
		request=EnslavedDataframesRequestSerializer
	)
	def post(self,request):
		print("ENSLAVED DATA FRAMES+++++++\nusername:",request.auth.user)
		st=time.time()
		
		print(request.data)
		#VALIDATE THE REQUEST
		serialized_req = EnslavedDataframesRequestSerializer(data=request.data)
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
			#FILTER THE ENSLAVED PEOPLE BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Enslaved.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Enslaved_options,
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
# 			print()
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,json.dumps(resp))
		else:
			if DEBUG:
				print("cached:",hashed)
			resp=json.loads(cached_response)
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
		
		return JsonResponse(resp,safe=False,status=200)

class EnslaverDataFrames(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The dataframes endpoint is mostly for internal use -- building up caches of data in the flask services.\n\
		However, it could be used for csv exports and the like.\n\
		Be careful! It's a resource hog. But more importantly, if you request fields that are not one-to-one relationships with the enslaver, you're likely to get back extra rows.\n\
		And finally, the example provided below puts a strict year filter on because unrestricted, it will break your swagger viewer :) \n\
		",
		request=EnslaverDataframesRequestSerializer
	)
	def post(self,request):
		print("ENSLAVER DATA FRAMES+++++++\nusername:",request.auth.user)
		st=time.time()
		
		#VALIDATE THE REQUEST
		serialized_req = EnslaverDataframesRequestSerializer(data=request.data)
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
			#FILTER THE ENSLAVERS BASED ON THE REQUEST'S FILTER OBJECT
			queryset=EnslaverIdentity.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				EnslaverIdentity_options,
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

class EnslavementRelationDataFrames(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="The dataframes endpoint is mostly for internal use -- building up caches of data in the flask services.\n\
		However, it could be used for csv exports and the like.\n\
		Be careful! It's a resource hog. But more importantly, if you request fields that are not one-to-one relationships, you're likely to get back extra rows.\n\
		And finally, the example provided below puts a strict year filter on because unrestricted, it will break your swagger viewer :) \n\
		",
		request=EnslavementRelationDataframesRequestSerializer
	)
	def post(self,request):
		print("+++++++\nusername:",request.auth.user)
		st=time.time()
		
		#VALIDATE THE REQUEST
		serialized_req = EnslavementRelationDataframesRequestSerializer(data=request.data)
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
			#FILTER THE ENSLAVERS BASED ON THE REQUEST'S FILTER OBJECT
			queryset=EnslavementRelation.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				EnslavementRelation_options,
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
		
class EnslaverGeoTreeFilter(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint is tricky. In addition to taking a filter object, it also takes a list of geographic value variable names, like 'aliases__enslaver_relations__relation__voyage__voyage_itinerary__port_of_departure__value'. \n\
		What it returns is a hierarchical tree of SlaveVoyages geographic data, filtered down to only the values used in those 'geotree valuefields' after applying A PARED DOWN VERSION OF the filter object.\n\
		So if you were to ask for aliases__enslaver_relations__relation__voyage__voyage_itinerary__port_of_departure__value, you would mostly get locations in Europe and the Americas; and if you searched 'aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__name', you would principally get places in the Americas and Africa.",
		request=EnslaverGeoTreeFilterRequestSerializer,
		responses=LocationSerializerDeep
	)
	def post(self,request):
		st=time.time()
		print("ENSLAVER GEO TREE FILTER+++++++\nusername:",request.auth.user)
		
		#CLEAN THE REQUEST'S FILTER (IF ANY)
		reqdict=dict(request.data)
		
		if 'filter' in reqdict:		
			for filteritem in list(reqdict['filter']):
				if filteritem['varName'] not in EnslaverBasicFilterVarNames:
					reqdict['filter'].remove(filteritem)
		
		#VALIDATE THE REQUEST
		serialized_req = EnslaverGeoTreeFilterRequestSerializer(data=reqdict)
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
			#extract and then peel out the geotree_valuefields
			geotree_valuefields=reqdict['geotree_valuefields']
			del(reqdict['geotree_valuefields'])
		
			#FILTER THE ENSLAVERS BASED ON THE REQUEST'S FILTER OBJECT
			queryset=EnslaverIdentity.objects.all()
			
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				reqdict,
				EnslaverIdentity_options,
				auto_prefetch=False,
				paginate=False
			)

			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))
		
			#THEN GET THE CORRESPONDING GEO VALUES ON THAT FIELD
			for geotree_valuefield in geotree_valuefields:
				geotree_valuefield_stub='__'.join(geotree_valuefield.split('__')[:-1])
				results=results.prefetch_related(geotree_valuefield_stub)
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

class EnslavedGeoTreeFilter(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint is tricky. In addition to taking a filter object, it also takes a list of geographic value variable names, like 'enslaved_relations__relation__voyage__voyage_itinerary__imp_port_voyage_begin__value'. \n\
		What it returns is a hierarchical tree of SlaveVoyages geographic data, filtered down to only the values used in those 'geotree valuefields' after applying the filter object.\n\
		So if you were to ask for enslaved_relations__relation__voyage__voyage_itinerary__imp_port_voyage_begin__value, you would mostly get locations in Europe and the Americas; and if you searched 'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__name', you would principally get places in the Americas and Africa.",
		request=EnslavedGeoTreeFilterRequestSerializer,
		responses=LocationSerializerDeep
	)
	def post(self,request):
		st=time.time()
		print("VOYAGE GEO TREE FILTER+++++++\nusername:",request.auth.user)
		#CLEAN THE REQUEST'S FILTER (IF ANY)
		reqdict=dict(request.data)
		if 'filter' in reqdict:		
			for filteritem in list(reqdict['filter']):
				if filteritem['varName'] not in EnslavedBasicFilterVarNames:
					reqdict['filter'].remove(filteritem)

		#VALIDATE THE REQUEST
		serialized_req = EnslavedGeoTreeFilterRequestSerializer(data=request.data)
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
			#extract and then peel out the geotree_valuefields
			reqdict=dict(request.data)
			geotree_valuefields=reqdict['geotree_valuefields']
			del(reqdict['geotree_valuefields'])
		
			#FILTER THE ENSLAVED PEOPLE BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Enslaved.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				reqdict,
				Enslaved_options,
				auto_prefetch=False,
				paginate=False
			)

			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			#THEN GET THE CORRESPONDING GEO VALUES ON THAT FIELD
			for geotree_valuefield in geotree_valuefields:
				geotree_valuefield_stub='__'.join(geotree_valuefield.split('__')[:-1])
				results=results.prefetch_related(geotree_valuefield_stub)
			vls=[]
			for geotree_valuefield in geotree_valuefields:		
				vls+=[i[0] for i in list(set(results.values_list(geotree_valuefield))) if i[0] is not None]
			vls=list(set(vls))
		
			#THEN GET THE GEO OBJECTS BASED ON THAT OPERATION
			resp=GeoTreeFilter(spss_vals=vls)
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

class EnslavedAggRoutes(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint provides a collection of multi-valued weighted nodes and splined, weighted edges. The intended use-case is the drawing of a geographic sankey map.",
		request=EnslavedAggRoutesRequestSerializer,
		responses=EnslavedAggRoutesResponseSerializer,
	)
	def post(self,request):
		st=time.time()
		print("ENSLAVED AGGREGATION ROUTES+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = EnslavedAggRoutesRequestSerializer(data=request.data)
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

			#FILTER THE ENSLAVED PEOPLE BASED ON THE REQUEST'S FILTER OBJECT
			params=dict(request.data)
			zoom_level=params.get('zoom_level')
			queryset=Enslaved.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Enslaved_options,
				auto_prefetch=True,
				paginate=False
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
				'cachename':'ao_maps',
				'pks':pks
			}
			r=requests.post(url=u2,data=json.dumps(d2),headers={"Content-type":"application/json"})
		
			#VALIDATE THE RESPONSE
			if r.ok:
				j=json.loads(r.text)
				serialized_resp=EnslavedAggRoutesResponseSerializer(data=j)
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

class PASTNetworks(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="This endpoint presents a graph database view of the highly interconnected data in PAST. We request the primary key of an enslaved person, an enslaver, a voyage, or an enslavement relation, and we receive back a pinhole view of the network in the form of the requested node and its neighbors (out to two hops for enslaved, one hop for all others) as well as the edges connecting these. You can request multiple nodes from multiple classes but the typical use case is to just request one and then iteratively grow the network. I shoudld probably put a cap on the total number of entities that can be requested.... The back-end is powered by <a herf='https://networkx.org/'>NetworkX</a>",
		request=PASTNetworksRequestSerializer,
		responses=PASTNetworksResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("PAST NETWORKS+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = PASTNetworksRequestSerializer(data=request.data)
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

			#HAND OFF TO THE FLASK CONTAINER
			params=json.dumps(dict(request.data))
			print(PEOPLE_NETWORKS_BASE_URL)
			r=requests.post(PEOPLE_NETWORKS_BASE_URL,data=params,headers={"Content-type":"application/json"})
		
			#VALIDATE THE RESPONSE
			if r.ok:
				j=json.loads(r.text)
				serialized_resp=PASTNetworksResponseSerializer(data=j)
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

######## READ-ONLY CONTROLLED VOCAB ENDPOINTS

class EnslaverRoleList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	'''
	model=EnslaverRole
	queryset=EnslaverRole.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=EnslaverRoleSerializer

class GenderList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	'''
	model=Gender
	queryset=Gender.objects.all()
	pagination_class=None
	sort_by='value'
	serializer_class=GenderSerializer

class CaptiveFateList(generics.ListAPIView):
	'''
	Controlled vocabulary, read-only.
	Not paginated; rather, we dump all the values out. Intended for use in a contribute form.
	
	'''
	model=CaptiveFate
	queryset=CaptiveFate.objects.all()
	pagination_class=None
	sort_by='name'
	serializer_class=CaptiveFateSerializer

class EnslaverGET(generics.RetrieveAPIView):
	'''
	Retrieve an enslaver record with their pk
	'''
	queryset=EnslaverIdentity.objects.all()
	serializer_class=EnslaverIdentitySerializer
	lookup_field='id'
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]

class EnslavedGET(generics.RetrieveAPIView):
	'''
	Retrieve an enslaver record with their pk
	'''
	queryset=Enslaved.objects.all()
	serializer_class=EnslavedSerializer
	lookup_field='enslaved_id'
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	
class EnslavedVoyageOutcome(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
# 	@extend_schema(
# 		description="Controlled vocabulary of voyage outcomes by enslaved individuals. Filterable only (for now) on voyage dataset.",
# 		request=EnslavedVoyageOutcomeRequestSerializer,
# 		responses=EnslavedVoyageOutcomeResponseSerializer
# 	)
	def post(self,request):
		st=time.time()
		print("ENSLAVED VOYAGE OUTCOME+++++++\nusername:",request.auth.user)
		
		#CLEAN THE REQUEST'S FILTER (IF ANY)
		reqdict=dict(request.data)
		
		EnslavedVoyageOutcomeFilterVarNames=['dataset','enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__name']
		
		if 'filter' in reqdict:		
			for filterItem in reqdict['filter']:
				print(filterItem)
				if filterItem['varName'] not in EnslavedVoyageOutcomeFilterVarNames:
					reqdict['filter'].remove(filterItem)
		
		#VALIDATE THE REQUEST
# 		serialized_req = EnslavedVoyageOutcomeRequestSerializer(data=reqdict)
# 		if not serialized_req.is_valid():
# 			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		if USE_REDIS_CACHE:
			srd=reqdict
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
			final_outcomesNamesList=list(eval(f"Enslaved.objects.all().values_list('enslaved_relations__relation__voyage__voyage_outcome__particular_outcome__value','enslaved_relations__relation__voyage__voyage_outcome__particular_outcome__name')"))
			if 'filter' in reqdict:
				if len(reqdict['filter'])>0:
					outcomesNamesLists=[]
					for filterItem in reqdict['filter']:
						varName=filterItem['varName']
						searchTerm=filterItem['searchTerm']
						op=filterItem['op']
						vlist=eval(f"Enslaved.objects.all().filter({varName}__{op}={searchTerm}).values_list('enslaved_relations__relation__voyage__voyage_outcome__particular_outcome__value','enslaved_relations__relation__voyage__voyage_outcome__particular_outcome__name')")
						outcomesNamesLists.append(list(vlist))
					fstrlist=[str(set(i)) for i in outcomesNamesLists]
					fstr=" & ".join(fstrlist)
# 					print(fstr)
					final_outcomesNamesList=list(eval(fstr))
			
			flattened={}
			for i in final_outcomesNamesList:
				flattened[i[0]]=i[1]

			resp=[
				{
					"value":i,
					"name":flattened[i]
				}
				for i in flattened
				if i is not None
			]
			
			if USE_REDIS_CACHE:
				redis_cache.set(hashed,json.dumps(resp))			
		else:
			if DEBUG:
				print("cached:",hashed)
			resp=json.loads(cached_response)
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
		
		return JsonResponse(resp,safe=False,status=200)

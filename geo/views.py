from django.shortcuts import render,get_object_or_404
from django.http import HttpResponse, JsonResponse
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
import time
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from django.views.generic.list import ListView
from .models import *
from .common import GeoTreeFilter
from drf_spectacular.utils import extend_schema
from .serializers import *
from voyages3.localsettings import REDIS_HOST,REDIS_PORT,DEBUG,USE_REDIS_CACHE
import redis
import hashlib

redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

class GeoTree(generics.GenericAPIView):
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		description="Fetch the generic tree of locations.",
		request=GeoTreeFilterRequestSerializer,
		responses=LocationSerializerDeep
	)
	def post(self,request):
		st=time.time()
		print("GEO TREE FILTER+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = GeoTreeFilterRequestSerializer(data=request.data)
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
		
			#THEN GET THE GEO OBJECTS BASED ON THAT OPERATION
			resp=GeoTreeFilter(select_all=True)
		
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
		
class LocationRETRIEVE(generics.RetrieveAPIView):
	'''
	The lookup field for geographic locations is "VALUE". This corresponds to the legacy SPSS codes used for geo data -- first for voyage itineraries and ship construction/registration locations, but later on for enslaved peoples\' origins and final known locations, as well as for Enslavers\' place of birth etc. In the legacy SV website db, these 'Locations' were stored as separate models, hierarchically ordered.
	
		1. Place
		2. Region
		3. Broad Region
	
	While the SPSS codes / "value" fields in these models were supposed to be unique, this was not always the case. I therefore decided to collapse these into a single model, enforce the uniqueness of the value fields, create a location_type model to store these locations, and store the hierarchical relation through a child_of foreign key.
	'''
	queryset=Location.objects.all()
	serializer_class=LocationSerializer
	lookup_field='value'
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
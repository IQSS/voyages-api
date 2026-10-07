from django.shortcuts import render,get_object_or_404
from django.http import HttpResponse, JsonResponse
from rest_framework.schemas.openapi import AutoSchema
from rest_framework import generics
import time
from rest_framework.metadata import SimpleMetadata
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.views.generic.list import ListView
from common.reqs import *
from .models import *
import hashlib
import redis
from .serializers import *
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from voyages3.localsettings import REDIS_HOST,REDIS_PORT,DEBUG,USE_REDIS_CACHE
from common.static.Institution_options import Institution_options
from common.static.Post_options import Post_options
from common.static.Author_options import Author_options
from common.serializers import autocompleterequestserializer, autocompleteresponseserializer


redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

class PostList(generics.GenericAPIView):
	'''
	The Voyages team launched its new blog interface in 2022, in order to allow for richer humanities content to be integrated into the site, and to allow for more rapid publication of project-related news.
	
	These blog posts come in 3 languages: English, Spanish, and Portuguese. The author writes in one language, and when they are posted, the text is sent to the Google Translate API. The translated content is then published as three separate posts. This allows the team to go back in and fine-tune translations. The output format is HTML.
	
	Blog posts also contain hyperlinks to images hosted by SlaveVoyages for making the posts visually appealing.
	'''
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		request=PostListRequestSerializer,
		responses=PostListResponseSerializer
	)
	def post(self,request):

		st=time.time()
		print("BLOG POST LIST+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = PostListRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
# 		if USE_REDIS_CACHE:
# 			srd=serialized_req.data
# 			hashdict={
# 				'req_name':str(self.request),
# 				'req_data':srd
# 			}
# 			hashed=hashlib.sha256(
# 				json.dumps(
# 					hashdict,
# 					sort_keys=True,
# 					indent=1
# 				).encode('utf-8')
# 			).hexdigest()
# 			cached_response = redis_cache.get(hashed)
# 		else:
# 			cached_response=None

		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
# 		if cached_response is None:
			#FILTER THE POSTS BASED ON THE REQUEST'S FILTER OBJECT
		queryset=Post.objects.all()
		results,results_count,page,page_size,error_messages=post_req(
			queryset,
			self,
			request,
			Post_options,
			auto_prefetch=True,
			paginate=True
		)
		
		if error_messages:
			return(JsonResponse(error_messages,safe=False,status=400))

		resp=PostListResponseSerializer({
			'count':results_count,
			'page':page,
			'page_size':page_size,
			'results':results
		}).data
			#SAVE THIS NEW RESPONSE TO THE REDIS CACHE
# 			if USE_REDIS_CACHE:
# 				redis_cache.set(hashed,json.dumps(resp))
# 		else:
# 			resp=json.loads(cached_response)
		
		if DEBUG:
			print("Internal Response Time:",time.time()-st,"\n+++++++")
			
		return JsonResponse(resp,safe=False,status=200)

class PostTextFieldAutoComplete(generics.GenericAPIView):
	'''
	The autocomplete endpoints provide paginated lists of values on fields related to the endpoints primary entity (here, the blog post). It also accepts filters.
	'''
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		request=PostAutoCompleteRequestSerializer,
		responses=PostAutoCompleteResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("BLOG POST CHAR FIELD AUTOCOMPLETE+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = PostAutoCompleteRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		if USE_REDIS_CACHE:
			srd=serialized_req.data
			hashdict={
				'req_name':str(self.request),
				'req_data':srd
			}
			hashed=hashlib.sha256(
				json.dumps(
					hashdict,
					sort_keys=True,
					indent=1
				).encode('utf-8')
			).hexdigest()
			cached_response = redis_cache.get(hashed)
		else:
			cached_response=None
		
		if cached_response is None:
			unfiltered_queryset=Post.objects.all()
			#RUN THE AUTOCOMPLETE ALGORITHM (WHICH ITSELF RUNS THE DJANGO FILTER)
			final_vals=autocomplete_req(unfiltered_queryset,self,request,Post_options,'Post')
			
			if "errors" in final_vals:
				return JsonResponse(final_vals['errors'],safe=False,status=400)
			
			resp=dict(request.data)
			resp['suggested_values']=final_vals
			#VALIDATE THE RESPONSE
			serialized_resp=PostAutoCompleteResponseSerializer(data=resp)
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

class AuthorList(generics.GenericAPIView):
	'''
		Blog authors are allowed to add a user profile image, affiliate themselves with a university, and give a brief bio of themselves (under the "description") field.
		
		The posts authored by the author are included in the response as an array of nested objects.
	'''
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		request=AuthorListRequestSerializer,
		responses=AuthorListResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("AUTHOR LIST+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = AuthorListRequestSerializer(data=request.data)
		if not serialized_req.is_valid():
			return JsonResponse(serialized_req.errors,status=400)

		#AND ATTEMPT TO RETRIEVE A REDIS-CACHED RESPONSE
		if USE_REDIS_CACHE:
			srd=serialized_req.data
			hashdict={
				'req_name':str(self.request),
				'req_data':srd
			}
			hashed=hashlib.sha256(
				json.dumps(
					hashdict,
					sort_keys=True,
					indent=1
				).encode('utf-8')
			).hexdigest()
			cached_response = redis_cache.get(hashed)
		else:
			cached_response=None
		
		#RUN THE QUERY IF NOVEL, RETRIEVE IT IF CACHED
		if cached_response is None:
			#FILTER THE AUTHORS BASED ON THE REQUEST'S FILTER OBJECT
			queryset=Author.objects.all()
			queryset,results_count=post_req(
				queryset,
				self,
				request,
				Author_options,
				auto_prefetch=True,
				paginate=True
			)
			
			resp=AuthorListResponseSerializer({
				'count':total_results_count,
				'page':page_num,
				'page_size':page_size,
				'results':results
			}).data
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

class InstitutionList(generics.GenericAPIView):
	'''
		The institutions that the blog authors are affiliated with can be searched in their own right.
		
		The authors associated with these institutions are included as nested objects, and the posts by those authors are nested within these author objects.
	'''
	authentication_classes=[TokenAuthentication]
	permission_classes=[IsAuthenticated]
	@extend_schema(
		request=InstitutionListRequestSerializer,
		responses=InstitutionListResponseSerializer
	)
	def post(self,request):
		st=time.time()
		print("INSTITUTION LIST+++++++\nusername:",request.auth.user)
		
		#VALIDATE THE REQUEST
		serialized_req = InstitutionListRequestSerializer(data=request.data)
		
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
			queryset=Institution.objects.all()
			results,results_count,page,page_size,error_messages=post_req(
				queryset,
				self,
				request,
				Institution_options,
				auto_prefetch=True,
				paginate=True
			)

			if error_messages:
				return(JsonResponse(error_messages,safe=False,status=400))

			resp=InstitutionListResponseSerializer({
				'count':results_count,
				'page':page,
				'page_size':page_size,
				'results':results
			},read_only=True).data
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
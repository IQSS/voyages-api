import time
import json
import pprint
import urllib
from django.db.models import Avg,Sum,Min,Max,Count,Q,F
from django.db.models.aggregates import StdDev
from voyages3.localsettings import OPEN_API_BASE_URL,DEBUG,SOLR_ENDPOINT,REDIS_HOST,REDIS_PORT,USE_REDIS_CACHE
import requests
from django.core.paginator import Paginator
from django.core.exceptions import FieldError
import html
import re
import pysolr
import redis
import os
import uuid
from past.models import *
from voyage.models import *
from blog.models import *
import pickle
import math
from document.models import Source
from common.autocomplete_indices import get_inverted_autocomplete_indices,autocomplete_indices,get_inverted_autocomplete_basic_index_field_endings
import hashlib

redis_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

#these need to present out, in all cases, as multiplied by 100
percentage_fields=[
	'voyage_slaves_numbers__child_ratio_among_embarked_slaves',
	'voyage_slaves_numbers__child_ratio_among_landed_slaves',
	'voyage_slaves_numbers__imp_mortality_ratio',
	'voyage_slaves_numbers__male_ratio_among_embarked_slaves',
	'voyage_slaves_numbers__male_ratio_among_landed_slaves',
	'voyage_slaves_numbers__percentage_adult',
	'voyage_slaves_numbers__percentage_boy',
	'voyage_slaves_numbers__percentage_boys_among_embarked_slaves',
	'voyage_slaves_numbers__percentage_boys_among_landed_slaves',
	'voyage_slaves_numbers__percentage_child',
	'voyage_slaves_numbers__percentage_female',
	'voyage_slaves_numbers__percentage_girl',
	'voyage_slaves_numbers__percentage_girls_among_embarked_slaves',
	'voyage_slaves_numbers__percentage_girls_among_landed_slaves',
	'voyage_slaves_numbers__percentage_male',
	'voyage_slaves_numbers__percentage_men',
	'voyage_slaves_numbers__percentage_men_among_embarked_slaves',
	'voyage_slaves_numbers__percentage_men_among_landed_slaves',
	'voyage_slaves_numbers__percentage_women',
	'voyage_slaves_numbers__percentage_women_among_embarked_slaves',
	'voyage_slaves_numbers__percentage_women_among_landed_slaves'
]

def clean_long_df(rows,selected_fields):
	'''
	JSON Serialization doesn't fly when you fetch the raw value of certain data types
	e.g., uuid.UUID, decimal.Decimal.....
	'''
	
	resp={sf:[] for sf in selected_fields}
	
	for i in range(len(selected_fields)):
		sf=selected_fields[i]
		column=[r[i] for r in rows]
		
		for r in rows:
			val=r[i]
			if type(val) == uuid.UUID:
				val=str(val)
			
			resp[sf].append(val)
	
	return resp
	
def paginate_queryset(queryset,request):
	'''
		Customized pagination for post requests. Params are:
		page_size (int)
		page (int)
	'''
	
	params=request.data
	page_size=params.get('page_size',10)
	page=params.get('page',1)
	paginator=Paginator(queryset, page_size)
	results_page=paginator.get_page(page)
	total_results_count=queryset.count()
	return results_page,total_results_count,page,page_size
	
def get_fieldstats(queryset,aggregation_field,options_dict):
	'''
		Used to get the min and max of a numeric field
		Takes a queryset (can be filtered), a field to be filtered on,
		and the list of valid variables for the queryset's base object class
		then uses django's aggregation functions to pull the min & max
		The mean is also available if we choose to extend this later
	'''
	res=None
	errormessages=[]
	
	if aggregation_field is None:
		errormessages.append("you must supply a field to aggregate on")
	else:
		valid_aggregation_fields=[f for f in options_dict if options_dict[f]['type'] in ['integer','number']]
		if aggregation_field not in valid_aggregation_fields:
			errormessages.append("bad aggregation field: " + aggregation_field)
		else:
			if '__' in aggregation_field:
				prefetch_name='__'.join(aggregation_field.split('__')[:-1])
				queryset=queryset.prefetch_related(prefetch_name)
				if DEBUG:
					print("prefetching:",prefetch_name)
			min=math.floor(queryset.aggregate(Min(aggregation_field)).popitem()[1])
			max=math.ceil(queryset.aggregate(Max(aggregation_field)).popitem()[1])
			
			if aggregation_field in percentage_fields:
				if min<=1:
					min=min*100
				if max<=1:
					max=max*100
			
			res={
				'varName':aggregation_field,
				'min':min,
				'max':max
			}
	return res,errormessages

solrcorenamedict={
	"<class 'voyage.models.Voyage'>":'voyages',
	"<class 'past.models.EnslaverIdentity'>":'enslavers',
	"<class 'past.models.Enslaved'>":'enslaved',
	"<class 'blog.models.Post'>":'blog',
	"<class 'document.models.Source'>":'sources'
}

def global_search(orig_queryset,search_string,core_name=None):
	# GLOBAL SEARCH
	## bypasses the normal filters. 
	## hits solr with a search string (which currently is applied across all text fields on a model)
	## and then creates its filtered queryset on the basis of the pk's returned by solr
	qsetclassstr=str(orig_queryset[0].__class__)
	if not core_name:
		core_name=solrcorenamedict[qsetclassstr]
	if DEBUG:
		print("CLASS",qsetclassstr,core_name)
	solr = pysolr.Solr(
		f'{SOLR_ENDPOINT}/{core_name}/',
		always_commit=True,
		timeout=10
	)
	search_string=re.sub("\s+"," ",search_string)
	search_string=search_string.strip()
	searchstringcomponents=[''.join(filter(str.isalnum,s)) for s in search_string.split(' ')]
	finalsearchstring="(%s)" %(" ").join(searchstringcomponents)
	results=solr.search('text:%s' %finalsearchstring,**{'rows':10000000,'fl':'id'})
	ids=[doc['id'] for doc in results.docs]
	filtered_queryset=orig_queryset.filter(id__in=ids)
	results_count=len(ids)
	return filtered_queryset,results_count



def post_req(orig_queryset,s,r,options_dict,auto_prefetch=True,paginate=False):
	'''
		This function handles:
		1. ensuring that all the fields that will be called are valid on the model
		2. applying filters to the queryset
		3. bypassing the normal usage and going to solr for pk's if 'global_search' is in the query data
		4. ordering the queryset
		5. attempting to intelligently prefetch related fields for performance
	'''
	
	nonquerysetkeysforredis=[
		"page",
		"page_size",
		"order_by"
	]
	
	st=time.time()
	
	error_messages=[]
	results_count=None
	
	all_fields={i:options_dict[i] for i in options_dict if options_dict[i]['type']!='table'}
	if type(r)==dict:
		params=r
	else:
		params=dict(r.data)
	
	filter_obj=params.get('filter') or {}
	
	if DEBUG:
		print(f"REQ PREP TIME: {time.time()-st}")
	
	if DEBUG:
		print("PRE FILTER COUNT",orig_queryset.count())
	
	
	#PREFETCH REQUISITE FIELDS
	prefetch_fields=params.get('selected_fields') or []
	if prefetch_fields==[] and auto_prefetch:
		prefetch_fields=list(all_fields.keys())
	#endswith field excludes solr fields
	prefetch_vars=list(set(['__'.join(i.split('__')[:-1]) for i in prefetch_fields if '__' in i and not i.endswith("__ALL")]))
	if DEBUG:
		print(f'--prefetch: {len(prefetch_vars)} vars--')
	for p in prefetch_vars:
		orig_queryset=orig_queryset.prefetch_related(p)
	
	# GLOBAL SEARCH
	## bypasses the normal filters. 
	## hits solr with a search string (which currently is applied across all text fields on a model)
	## and then creates its filtered queryset on the basis of the pk's returned by solr
	qsetclassstr=str(orig_queryset[0].__class__)
	
	#patch for enslaver fields, aug 14, 2025
	#performance hits on the below fields. we redirect to new names when these come in
	#can probably retire this once saved queries using these vars are patched
	bad_field_map={
		"aliases__enslaver_relations__roles__name":"roles__name",
		"aliases__enslaver_relations__relation__voyage__dataset":"voyages__dataset",
		"aliases__enslaver_relations__relation__voyage__voyage_ship__ship_name":"voyages__voyage_ship__ship_name",
		"aliases__enslaver_relations__relation__voyage__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year":"voyages__voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
		"aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_port_voyage_begin__value":"voyages__voyage_itinerary__imp_port_voyage_begin__value",
		"aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__value":"voyages__voyage_itinerary__imp_principal_region_of_slave_purchase__value",
		"aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__value":"voyages__voyage_itinerary__imp_principal_port_slave_dis__value"
	}
	
	if 'global_search' in params:
		filtered_queryset,results_count=global_search(orig_queryset,params['global_search'])
	# SPECIAL CASE SEARCH/FILTER
	else:
		st=time.time()
		kwargs={}
		ids=[]
		filtered_queryset=orig_queryset
		c=0
		
		# SPECIAL CASE 1: ENSLAVERS AND ASSOCIATED ROLES
		for item in filter_obj:
			op=item['op']
			searchTerm=item["searchTerm"]
			varName=item["varName"]
			if varName=="HasLinkedVoyages":
				linkedvoyage=None
				if searchTerm in [1,0,"1","0",True,False,"True","False","true","false","T","F"]:
					linkedvoyage=True
				elif searchTerm in [1,0,"1","0",True,False,"True","False","true","false","T","F"]:
					linkedvoyage=False
				
				if linkedvoyage is not None:	
					qobjstr=f'Q(outgoing_to_other_voyages__isnull={linkedvoyage})|Q(incoming_from_other_voyages__isnull={linkedvoyage})'
					filtered_queryset=f'filtered_queryset.filter({qobjstr})'
			if varName=="EnslaverNameAndRole":
				class_name=solrcorenamedict[qsetclassstr]
				searchTerm=searchTerm[0]
				name=searchTerm['name']
				roles=searchTerm['roles']
				if class_name=='voyages':
					# we need to get hits for the below formats
					# because the data has not always been added inconsistently
					# and the users don't know the difference
					## lastname, firstname
					## firstname lastname
					namesegments=[re.sub('[,|.| ]','',n) for n in name.split(" ") if re.sub('[,|.| ]','',n)!='']
					# so we filter on each chunk of the name, serially, stripped of punctuation
					qobjstrs=[]
					for namesegment in namesegments:
						qobjstr=f'Q(voyage_enslavement_relations__relation_enslavers__enslaver_alias__alias__icontains="{namesegment}")|\
								Q(voyage_enslavement_relations__relation_enslavers__enslaver_alias__identity__principal_alias__icontains="{namesegment}")'
						qobjstrs.append(qobjstr)
					qobjstr=' , '.join(qobjstrs)
					execobjstr=f'filtered_queryset.filter({qobjstr})'
					print("EXECOBJSTR",execobjstr)
					enslavernamehits=eval(execobjstr)
					ids=[]
					enslaverinrelationnamehits=[]
					for enslavernamehit in enslavernamehits:
						ers=enslavernamehit.voyage_enslavement_relations.all()
						for er in ers:
							eirs_unfiltered=er.relation_enslavers.all()
							qobjstrs=[]
							for namesegment in namesegments:
								qobjstr=f'Q(enslaver_alias__alias__icontains="{namesegment}")|Q(enslaver_alias__identity__principal_alias__icontains="{namesegment}")'
								qobjstrs.append(qobjstr)
							qobjstr=' , '.join(qobjstrs)
							execobjstr=f'eirs_unfiltered.filter({qobjstr})'
							eirs=eval(execobjstr)
							for eir in eirs:
								enslavernamehitroles=[v[0] for v in eir.roles.all().values_list("name")]
								hit=False
								if op=="andlist":
									hit=False
									if set(enslavernamehitroles)>=set(roles):
										ids.append(enslavernamehit.id)
										hit=True
								elif op=="in":
									if len(set(enslavernamehitroles)&set(roles))>0:
										ids.append(enslavernamehit.id)
										hit=True
					ids=list(set(ids))
					filtered_queryset=filtered_queryset.filter(id__in=ids)
					filter_obj.remove(item)
			# SPECIAL CASE 2: DOCUMENTARY SOURCES
			if varName.endswith("__source__ALL"):
				qsetclassstr=str(orig_queryset[0].__class__)
				if solrcorenamedict[qsetclassstr]=='voyages':
					filtered_queryset,results_count=global_search(orig_queryset,searchTerm,core_name='voyagesources')
				elif solrcorenamedict[qsetclassstr]=='enslavers':
					filtered_queryset,results_count=global_search(orig_queryset,searchTerm,core_name='enslaversources')
				elif solrcorenamedict[qsetclassstr]=='enslaved':
					filtered_queryset,results_count=global_search(orig_queryset,searchTerm,core_name='enslavedsources')
				
				filter_obj.remove(item)
		# TYPICAL ORM-BASED SEARCH/FILTER
		for item in filter_obj:
			#construct the django-style search on any related field
			op=item['op']
			varName=item["varName"]
			searchTerm=item["searchTerm"]
			print(varName,varName in percentage_fields)
			if varName in percentage_fields:
				if type(searchTerm)==list:
					searchTerm=[i/100 for i in searchTerm]
				else:
					searchTerm=searchTerm/100
				print(searchTerm)
			
			#swap out bad fields (aug 14, 2025)
			if varName in bad_field_map:
				varName=bad_field_map[varName]
				varNamestub='__'.join(varName.split('__')[:-1])
				filtered_queryset=filtered_queryset.prefetch_related(varNamestub)
			if op in ['lte','gte','exact','in','icontains']:
				django_filter_term='__'.join([varName,op])
				kwargs[django_filter_term]=searchTerm
			elif op == ['andlist']:
				for st in searchTerm:
					filterQ=f'filtered_queryset.filter({varName}={searchTerm})'
					print(filterQ)
					filtered_queryset=eval(filterQ)
			elif op =='btw':
				if type(searchTerm)==list and len(searchTerm)==2:
					searchTerm.sort()
					min,max=searchTerm
					kwargs['{0}__{1}'.format(varName, 'lte')]=max
					kwargs['{0}__{1}'.format(varName, 'gte')]=min		
				else:
					error_messages.append(f"Invalid Filter Item: {item} -> btw operations require that the searchterm a list of 2 numbers")
			else:
				error_messages.append(f"Invalid Filter Item Operation: {item}")
			
			try:
				print("kwargs-->",kwargs)
				filtered_queryset=filtered_queryset.filter(**kwargs)
			except Exception as e:
				badfielderrormessage=f"Invalid Filter Item: {item} -> {e}"
				error_messages.append(badfielderrormessage)
		
		if DEBUG:
			print(f"REQ FILTER TIME: {time.time()-st}")
		
	
	# ORDER RESULTS
	st=time.time()
	pre_order_by_count=filtered_queryset.count()
	order_by=params.get('order_by')
	if order_by is not None:
		if DEBUG:
			print(f"------>ORDER BY: {order_by}")
		obl=[]
		for ob in order_by:
			if ob.startswith('-'):
				k=ob[1:]
				ascdesc='asc'
			else:
				ascdesc='desc'
				k=ob
			if k in all_fields:
				obl.append(k)
			else:
				print(f"key is invalid to sort on: {k}")
			
			oblstr=','.join([f"F('{k}').{ascdesc}(nulls_last=True)" for k in obl])
			
			qfilterstr=f"filtered_queryset.order_by({oblstr})"
			filtered_queryset=eval(qfilterstr)
			
	else:
		filtered_queryset=filtered_queryset.order_by('id')
	
	if DEBUG:
		print(f"ORDER BY TIME: {time.time()-st}")
	
	post_order_by_count=filtered_queryset.count()
	
	st=time.time()
	# n.b. ordering on a many related field can create duplicates. we handle this later.
	## dedupe ordered results (while retaining the order)
	## https://stackoverflow.com/questions/480214/how-do-i-remove-duplicates-from-a-list-while-preserving-order
	
# 	if post_order_by_count>pre_order_by_count:
	dedupe=True
# 	else:
# 		dedupe=False
		
	if dedupe:
		ids=[v[0] for v in filtered_queryset.values_list('id')]
		ids=list(dict.fromkeys(ids))
		if DEBUG:
			print(f"DEDUPE TIME: {time.time()-st}")
	
	if dedupe:
		results_count=len(ids)
	else:
		results_count=filtered_queryset.count()
		
	if DEBUG:
		print("COUNT W/O DUPLICATES:",results_count)
		
	st=time.time()
	if paginate:
		page_size=params.get('page_size',10)
		page=params.get('page',1)
		print("PAGINATION:",paginate, page_size,page)
		if page<0:
			page=1
		page=page-1
		offset=page*page_size
		
		end_idx=offset+page_size
		if end_idx>=results_count:
			end_idx=results_count
		if offset>results_count:
			results=[]
		else:
			if dedupe:
				page_ids=ids[offset:end_idx]
				results=orig_queryset.filter(id__in=page_ids)
			else:
				results=filtered_queryset[offset:end_idx]
	else:
		if dedupe:
			results=orig_queryset.filter(id__in=ids)
		else:
			results=filtered_queryset
		page=None
		page_size=None
	
	if DEBUG:
		print(f"FILTER ON IDS TIME: {time.time()-st}")
		print(f"FINAL RESULTS COUNT: {results_count}")

	return results,results_count,page,page_size,error_messages

def getJSONschema(base_obj_name,hierarchical=False,rebuild=False):
	'''
	Recursively walks the OpenAPI schemas to build flat json files that we can later use for indexing, serializer population and validation, etc.
	Its best friend is the rebuild_options management command.
	Why do this? It turns out that the OpenAPI endpoint is a little touchy, so we can't route live requests through it.
	'''
	if hierarchical in [True,"true","True",1,"t","T","yes","Yes","y","Y"]:
		hierarchical=True
	else:
		hierarchical=False
	r=requests.get(url=OPEN_API_BASE_URL+"schema/?format=json")
	j=json.loads(r.text)
	schemas=j['components']['schemas']
	base_obj_name=base_obj_name
	def walker(output,schemas,obj_name,ismany=False):
		obj=schemas[obj_name]
		if 'properties' in obj:
			for fieldname in obj['properties']:
				thisfield=obj['properties'][fieldname]
				if 'allOf' in thisfield:
					thisfield=thisfield['allOf'][0]
# 					print(fieldname,'allof') ## OK THESE ARE M2M
					ismany=True
				if '$ref' in thisfield:
					next_obj_name=thisfield['$ref'].replace('#/components/schemas/','')
					output[fieldname]=walker({},schemas,next_obj_name,ismany)
# 					print(fieldname,'ref')
				elif 'type' in thisfield:
					if thisfield['type']!='array':
						thistype=thisfield['type']
						if 'format' in thisfield:
							if thisfield['format']:
								thistype='number'
						output[fieldname]={
							'type':thistype,
							'many':ismany
						}
# 						print(fieldname,'bottomval')
					else:
						thisfield_items=thisfield['items']
						if 'type' in thisfield_items:
# 							print('array otherbottomvalue',thisfield)
							output[fieldname]={
								'type':thisfield_items['type'],
								'many':ismany
							}
						elif '$ref'	in thisfield_items:
# 							print("array, ref???",thisfield)
							next_obj_name=thisfield_items['$ref'].replace('#/components/schemas/','')
							output[fieldname]=walker({},schemas,next_obj_name,ismany=True)
			ismany=False
		else:
			print(obj)
		return output
	
	output=walker({},schemas,base_obj_name)
		
	if not hierarchical:
		def flatten_this(input_dict,output_dict,keychain=[]):
			for k in input_dict:
				if 'type' in input_dict[k]:
					thiskey='__'.join(keychain+[k])
					output_dict[thiskey]=input_dict[k]
				else:
					output_dict=flatten_this(input_dict[k],output_dict,keychain+[k])
			return output_dict		
		output=flatten_this(output,{},[])
	
	if rebuild or not os.path.exists('./common/static/'+base_obj_name+"_options.json") or not os.path.exists('./common/static/'+base_obj_name+"_options.py"):
		flat_output=flatten_this(output,{},[])
		d=open('./common/static/'+base_obj_name+"_options.json",'w')
		d.write(json.dumps(flat_output))
		d.close()
		
		d=open('./common/static/'+base_obj_name+"_options.py",'w')
		d.write(base_obj_name+'_options='+str(flat_output))
		d.close()

	
	return output

def autocomplete_req(queryset,self,request,options,sourcemodelname):
	
	#first, get the reqdata
	if type(request)==dict:
		rdata=request
	else:
		rdata=dict(request.data)
		
	varName=str(rdata.get('varName'))
	querystr=str(rdata.get('querystr'))
	offset=int(rdata.get('offset'))
	limit=int(rdata.get('limit'))
	
	#then load the appropriate solr core to assist
	inverted_autocomplete_indices=get_inverted_autocomplete_indices()
	inverted_autocomplete_basic_index_field_endings=get_inverted_autocomplete_basic_index_field_endings()
	
	##USE SOLR
	if (sourcemodelname,varName) in inverted_autocomplete_indices:
		inverted_autocomplete_index=inverted_autocomplete_indices[(sourcemodelname,varName)]
		core_name=inverted_autocomplete_index['core_name']
		ac_field_model=inverted_autocomplete_index['model']
		model_searchfield=inverted_autocomplete_index['fields']

		#now get the pk's of the object from solr
		#if we do have some text to work with, then run the solr search
		solr = pysolr.Solr(
			f'{SOLR_ENDPOINT}/{core_name}/',
			always_commit=True,
			timeout=10
		)
		querystr=re.sub("\s+"," ",querystr)
		querystr=querystr.strip()
		searchstringcomponents=[''.join(filter(str.isalnum,s)) for s in querystr.split(' ')]
		finalsearchstring="(%s)" %(" ").join(searchstringcomponents)

		if finalsearchstring=="()":
			results=solr.search('text:*',**{'rows':10000000,'fl':'id'})
		else:
			results=solr.search('text:%s' %finalsearchstring,**{'rows':10000000,'fl':'id'})
		solr_ids=set([doc['id'] for doc in results.docs])
		#now we get the primary keys of that variable name from the filtered queryset
		#for example, if i'm searching in the trans-atlantic database, then I shouln't get any hits for 'OMNO'
		
		if "__" in varName:
			decomposed_varname=varName.split('__')
			varName_pkfield='__'.join(decomposed_varname[:-1])+"__id"
		else:
			varName_pkfield='id'
		
		filtered_queryset,results_count,page,page_size,error_messages=post_req(
			queryset,
			self,
			request,
			options,
			auto_prefetch=False
		)
		
		if error_messages:
			return({"errors":error_messages})
		
		varName_pks=[i[0] for i in filtered_queryset.values_list(varName_pkfield)]

		varName_pks=set(varName_pks)
		
		#now take the intersection of those sets
		##to recap, i've, for example,
		####used solr to get the full list of sources on a text search for 'omno'
		####hit the orm to get all the full list of applicable source pk's, say, in the intra-american db
		####and now i want to see where the overlap is
		results_ids=list(solr_ids & varName_pks)
		print(len(solr_ids),len(varName_pks),len(results_ids))
		ac_suggestions=[v[0] for v in ac_field_model.objects.all().filter(id__in=results_ids).order_by(model_searchfield).values_list(model_searchfield) if v[0] is not None]
		paginated_ac_suggestions=ac_suggestions[offset:(offset+limit)]
		
		response=[{"value":v} for v in paginated_ac_suggestions]
	else:
		targetmodelname=inverted_autocomplete_basic_index_field_endings[sourcemodelname][varName]
		fieldtail=re.sub('.*?__','',varName)
		queryset=eval(f'{targetmodelname}.objects.all()')
		
		filtered_queryset,results_count,page,page_size,error_messages=post_req(
			queryset,
			self,
			request,
			options,
			auto_prefetch=False
		)
		
		if error_messages:
			# return({"errors":error_messages})
			filtered_queryset=queryset
		evalstr=f'filtered_queryset.values_list("{fieldtail}")'
		acvals=eval(evalstr)
		listacvals=[v[0] for v in list(acvals)]
		listacvals.sort()
		response=[{"value":str(v)} for v in listacvals]
	return response

def use_redis(serialized_req,self):
		
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
		hashed=None
	return hashed,cached_response
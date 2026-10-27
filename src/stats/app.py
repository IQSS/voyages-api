import time
from flask import Flask,jsonify,request,abort,g,Response
import pandas as pd
import numpy as np
import json
import math
import requests
from localsettings import *
from index_vars import *
import re
from io import BytesIO
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

REQUEST_COUNT = Counter(
	'sv_http_requests_total',
	'Total HTTP requests handled by Slave Voyages services.',
	['service', 'framework', 'endpoint', 'method', 'status']
)
REQUEST_LATENCY = Histogram(
	'sv_http_request_duration_seconds',
	'HTTP request latency for Slave Voyages services.',
	['service', 'framework', 'endpoint', 'method'],
	buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

@app.before_request
def _start_request_timer():
	g._prometheus_started_at = time.perf_counter()


@app.after_request
def _record_request_metrics(response):
	started_at = getattr(g, '_prometheus_started_at', None)
	if started_at is None:
		return response
	endpoint = request.url_rule.rule if request.url_rule is not None else request.path
	method = request.method.upper()
	status = str(getattr(response, 'status_code', 500))
	REQUEST_COUNT.labels('voyages-stats', 'flask', endpoint, method, status).inc()
	REQUEST_LATENCY.labels('voyages-stats', 'flask', endpoint, method).observe(time.perf_counter() - started_at)
	return response


@app.route('/metrics')
def metrics():
	return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

def re_cleanup(re_dict,val):
	if val is not None:
		val=re.sub(
			re_dict['find'],
			re_dict['replace'],
			val,
			flags=re_dict['flags']
		)
	return val


def load_long_df(endpoint,variables):
	headers={'Authorization':DJANGO_AUTH_KEY,'Content-Type': 'application/json'}
	listval_vars={}
	for v in list(variables):
		listval=[]
		if variables[v]['type']=="obj":
			listval_vars[v]=variables[v]
	r=requests.post(
		url=DJANGO_BASE_URL+endpoint,
		headers=headers,
		data=json.dumps({'selected_fields':[
			v for v in variables if v not in listval_vars
		],'filter':[]})
	)
	j=json.loads(r.text)
	df=pd.DataFrame.from_dict(j)
	#coerce datatypes based on options call
	for varName in variables:
		vartype=variables[varName]['type']	
		if vartype in ["int","pct"]:
			df[varName]=pd.to_numeric(df[varName])
		
	#handle fields that
	##1. are m2m and produce duplicates w a values_list call
	##2. need to be stuffed into an object field in pandas
	##3. need a regex cleanup
	
	rolluptime=0
	dftime=0
	
	for v in listval_vars:
		print(v,listval_vars[v])
		df[v]=np.nan
		df[v]=df[v].astype(str)
		fields=["id"]+listval_vars[v]['fields']
		if 'join' in listval_vars[v]:
			fieldjoin=listval_vars[v]['join']
		else:
			fieldjoin=": "
		r=requests.post(
			url=DJANGO_BASE_URL+endpoint,
			headers=headers,
			data=json.dumps({'selected_fields':[v for v in fields],'filter':[]})
		)
		j=json.loads(r.text)
		# pull out m2m fields and join them (as strings)
		rollup={}
		if "re_cleanup" in listval_vars[v]:
			cleanup=listval_vars[v]['re_cleanup']
		else:
			cleanup=None
		if cleanup:
			print("CLEANUP",v,cleanup)
		jkeys=list(j.keys())
		for i in range(len(j[jkeys[0]])):
			idnum=j[jkeys[0]][i]
			itemvals=[
				re_cleanup(cleanup,j[k][i]) if cleanup else j[k][i]
				for k in jkeys[1:]
			]
			if itemvals:
				item=fieldjoin.join([
					"" if itemval is None else str(itemval)
					for itemval in itemvals
				])
				if idnum in rollup:
					rollup[idnum].append(item)
				else:
					rollup[idnum]=[item]
		
		for i in rollup:
			row=df[df['id']==i]
			idx=row.index[0]
			obj='|'.join(rollup[i])
			df.iloc[idx,df.columns.get_loc(v)]=obj
	
	return(df)

registered_caches=[
	big_df,
	estimate_pivot_tables,
	timelapse
]

replaced_dfs=[
	"voyage_bar_and_donut_charts",
	"voyage_summary_statistics",
	"voyage_pivot_tables",
	"voyage_xyscatter"
]

#on initialization, load every index as a dataframe, via a call to the django api
st=time.time()

standoff_base=4
standoff_count=0
while True:
	failures_count=0
	for rc in registered_caches:
		time.sleep(1)
		#pull the index keys from the index_vars.py file
		#and load each cache based on the parameters it sets out
		endpoint=rc['endpoint']
		variables=rc['variables']
		rcname=rc['name']
		schema_name=rc['schema_name']
		headers={'Authorization':DJANGO_AUTH_KEY,'Content-Type': 'application/json'}
		#before we make the dataframes call, we need to get the schema data
		#via an options call to the django server
		#because this will allow us to coerce the propert data types (numeric or categorical)
		#in order to make the math work out properly later!
# 		try:
		rc['options']=variables
		thisdf=load_long_df(endpoint,variables)
		#timelapse needs is na entries filled ahead of time
		if rcname=='timelapse':
			for varName in variables:
				vartype=variables[varName]['type']
				if vartype in [
					"int",
					"pct"
				]:
					thisdf[varName]=thisdf[varName].fillna(0)
					thisdf[varName]=thisdf[varName].astype('int')
				else:
					thisdf[varName]=thisdf[varName].fillna('')
		#periods cause problems
		rc['df']=thisdf
		print(rc['df'])
# 		except:
# 			failures_count+=1
# 			print("failed on cache:",rcname)
	print("failed on %d of %d caches" %(failures_count,len(registered_caches)))
	if failures_count==len(registered_caches):
		standoff_time=standoff_base**standoff_count
		print("retrying after %d seconds" %(standoff_time))
		time.sleep(standoff_time)
		standoff_count+=1
	else:
		break

print("finished building stats indices in %d seconds" %int(time.time()-st))


#we need to make the indices' contents visible
@app.route('/get_indices/')
def get_indices():
	resp={}
	for rc in registered_caches:
		resp[rc['name']]=rc['variables']
	return json.dumps(resp)


@app.route('/timelapse/',methods=['POST'])
def timelapse_animation():

	'''
	https://www.slavevoyages.org/voyage/database#timelapse
	'''
	st=time.time()
	rdata=request.json
	ids=rdata['ids']
	df=timelapse['df']
	df=df[df['id'].isin(ids)]
	
	colname_map={'id': 'voyage_id', 'voyage_ship__imputed_nationality__id':'nat_id','voyage_itinerary__imp_principal_place_of_slave_purchase__id': 'src', 'voyage_itinerary__imp_principal_port_slave_dis__id': 'dst', 'voyage_itinerary__imp_principal_region_of_slave_purchase__id': 'regsrc', 'voyage_itinerary__imp_broad_region_of_slave_purchase__id': 'bregsrc', 'voyage_itinerary__imp_principal_region_slave_dis__id': 'regdst', 'voyage_itinerary__imp_broad_region_slave_dis__id': 'bregdst', 'voyage_slaves_numbers__imp_total_num_slaves_embarked': 'embarked', 'voyage_slaves_numbers__imp_total_num_slaves_disembarked': 'disembarked', 'voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year': 'year', 'voyage_dates__imp_arrival_at_port_of_dis_sparsedate__month': 'month', 'voyage_ship__tonnage_mod': 'ship_ton', 'voyage_ship__imputed_nationality__value': 'nat_id', 'voyage_ship__ship_name': 'ship_name'}
	
	df=df.rename(columns=colname_map)
# 	print(df)
	return df.to_json(orient="records")

@app.route('/groupby/',methods=['POST'])
def groupby():
	'''
	Implements the pandas groupby function and returns the sparse summary.
	Excellent for bar, pie, and scatter charts.
	'''
	st=time.time()
	rdata=request.json
	ids=rdata['ids']
	by=rdata['by']
	val=rdata['vals']
	agg_fn=rdata['agg_fn']
	binsize=None
	if re.match("[a-z|_]+__bins__[0-9]+",by):
		binsize=int(re.search("[0-9]+",by).group(0))
		by=re.search("[a-z|_]+(?=__bins__)",by).group(0)
	df=big_df['df']
	df2=df[df['id'].isin(ids)]
	
	##TBD --> NEED TO VALIDATE THAT THE ROWS VARIABLE IS
	####1) NUMERIC TO WORK IN THE FIRST PLACE
	####2) A YEAR VAR IN ORDER TO MAKE SENSE TO A HUMAN END-USER
	if binsize is not None:
		binrows=by
		binsize=int(binsize)
		df2=df2.dropna(subset=[binrows])
		df2[binrows]=df2[binrows].astype('int')
		binvar_min=df2[binrows].min()
		binvar_max=df2[binrows].max()
		binvar_ints=list(range(int(binvar_min),int(binvar_max)+1))
		if binvar_max-binvar_min <=binsize:
			nbins=1
		else:
			nbins=int((binvar_max-binvar_min)/binsize)+1
		
		bin_tuples=[]
		for nbin in range(nbins):
			nbinmin=binvar_min+(binsize*nbin)
			nbinmax=binvar_min+(binsize*(nbin+1))-1
			if nbinmax>=binvar_max:
				nbinmax=binvar_max
			thisbin=(nbinmin,nbinmax)
			bin_tuples.append(thisbin)
		bins=pd.IntervalIndex.from_tuples(bin_tuples,closed='both')
		
		df2=df2.assign(row_bins=pd.cut(df2[by],bins,include_lowest=True))
		df2=df2[[val]+['row_bins']]
		df2=df2.rename(columns={"row_bins": by})
		gb=df2.groupby(by,group_keys=True).agg(agg_fn)
		gb=gb.fillna(0)
		
		idx=[re.sub(", ","-",re.sub(r"[\[|\]]","",str(i))) for i in gb.index]
		vs=list(gb[val])
		resp={
			by:idx,
			val:vs
		}
	else:
		gb=df2.groupby(by,group_keys=True)[[val]].agg(agg_fn)
		gb=gb.fillna(0)
		resp={by:list(gb.index)}
		resp[val]=list(gb[val])
			
	return json.dumps(resp)

#https://stackoverflow.com/questions/26033301/make-pandas-dataframe-to-a-dict-and-dropna
class NotNanDict(dict):
	@staticmethod
	def is_nan(v):
		if isinstance(v, dict):
			return False
		return np.isnan(v)

	def __new__(self, a):
		return {
			k: v for k, v in a if not self.is_nan(v) and v!={}
		}

def interval_to_str(s):
	s=str(s)
	adashb=re.sub('[\s,]+','-',re.sub('[\[\]]','',s))
	splitab=adashb.split('-')
	if splitab[0]==splitab[1]:
		return splitab[0]
	else:
		return adashb
	
def makestr(s):
	if s is None:
		return "Unknown"
	else:
		return str(s)

@app.route('/voyage_summary_stats/',methods=['POST'])
def voyage_summary_stats():

	'''
	https://www.slavevoyages.org/voyage/database#statistics
	'''
	st=time.time()
	rdata=request.json
	ids=rdata['ids']
	df=big_df['df']
	
	imputed_rows={
		'voyage_slaves_numbers__imp_total_num_slaves_embarked':'Captives embarked (Imputed)',
		'voyage_slaves_numbers__imp_total_num_slaves_disembarked':'Captives disembarked (Imputed)',
	}
	non_imputed_rows={
		'voyage_slaves_numbers__imp_mortality_ratio':'Percentage of captives embarked who died during crossing',
		'voyage_dates__length_middle_passage_days':"Duration of captives' crossing (in days)",
		'voyage_slaves_numbers__percentage_male':'Percentage male',
		'voyage_slaves_numbers__percentage_female':'Percentage female',
		'voyage_slaves_numbers__percentage_child':'Percentage children',
		'voyage_ship__tonnage_mod':'Tonnage of vessel'
	}
	
	#filter down on the pk's
	df=df[df['id'].isin(ids)]
	
	outputrecords=[]
	
	theaders=[
		''
		'Total captives',
		'Total voyages with this datapoint'
		'Average',
		'Median',
		'Standard deviation'
	]
	
	percentagerowkeys=[
		'voyage_slaves_numbers__imp_mortality_ratio',
		'voyage_slaves_numbers__percentage_male',
		'voyage_slaves_numbers__percentage_child',
		'voyage_slaves_numbers__percentage_female'
	]
	
	for k in imputed_rows:
		v=imputed_rows[k]
		record={'index':v}
		record['Total captives']=f'{int(df[k].sum()):,}'
		record['Total voyages with this datapoint']=f'{int(df[k].dropna().shape[0]):,}'
		
		average=str(round(df[k].mean(),1))
		if average=="nan":
			average=""
		
		median=str(round(df[k].median(),1))
		if median=="nan":
			median=""
		
		std=str(round(df[k].std(),1))
		if std=="nan":
			std=""
		
		record['Average']=average
		record['Median']=median
		record['Standard deviation']=std
		outputrecords.append(record)
	
	for k in non_imputed_rows:
		v=non_imputed_rows[k]
		record={'index':v}
		record['Total captives']=''
		record['Total voyages with this datapoint']=f'{int(df[k].dropna().shape[0]):,}'
		
		average=df[k].mean()
		median=df[k].median()
		std=df[k].std()
		
		if k in percentagerowkeys:
			average=str(round(average*100,1))
			median=str(round(median*100,1))
			
			if str(std)=="nan":
				std=""
			else:
				std=str(round(std*100,1))
				std=f'{std}%'
			
			if str(average)=="nan":
				average=""
			else:
				average=f'{average}%'
			
			if str(median)=="nan":
				median=""
			else:
				median=f'{median}%'
			
		else:
			if str(average)=="nan":
				average=""
			else:
				average=str(round(average,1))
			
			if str(median)=="nan":
				median=""
			else:
				median=str(round(median,1))
			
			if str(std)=="nan":
				std=""
			else:
				std=str(round(std))
			
		record['Average']=average
		record['Median']=median
		record['Standard deviation']=std
		outputrecords.append(record)
	
	headers=[
		'Total captives',
		'Total voyages with this datapoint',
		'Average',
		'Median',
		'Standard deviation'
	]
	
	headertablerow="".join([f'<th>{h}</th>' for h in headers])
	
	headertablerowhtml=f'<thead><tr style="text-align: right;"><th></th>{headertablerow}</tr></thead>'
	
	rowshtml=''
	
	for r in outputrecords:
		indexname=r['index']
		row="".join([f'<td>{r[h]}</td>' for h in headers])
		rowhtml=f"<tr><td>{indexname}</td>{row}</tr>"
		rowshtml+=rowhtml
	
	table=f'<table border="1" class="dataframe">{headertablerowhtml}{rowshtml}</table>'
	
	outputrecords.append(record)
	
	return json.dumps(
		{
			"data":table
		}
	)

@app.route('/estimates_pivot/',methods=['POST'])
def estimates_pivot():

	'''
	
	Compare this to the crosstabs endpoint below that's used for voyage pivot tables.
	
	We cannot implement multi-level rows in AG Grid
		1. because it's in the enterprise version
		2. because it's ugly
	It is possible that this is the implementation I was looking for all along.
	
	However, I don't know how to manage a multi-level column sort if we go this route.
	
	'''
	st=time.time()
	rdata=request.json
	ids=rdata['ids']
	rows=rdata['rows']
	cols=rdata['cols']
	vals=rdata['vals']
	binsize=rdata.get('binsize')
	mode=rdata['mode']
	df=estimate_pivot_tables['df']
	
	#filter down on the pk's
	pv=df[df['id'].isin(ids)]
	
	if len(pv)==0:
		
		html="<table border=\"1\"><tr><td>No results.</td></tr></table>"
		
	else:
	
		pv=pv.fillna(0)
		
		#force ints
		for val in vals:
			pv[val]=pv[val].astype('int')
		
		#handle a duplicate varname request like
		#rows=['nation__name'],cols=['nation__name']
		#which is dumb, because who wants a diagonal matrix???
		duplicate_indices=[i for i in cols if i in rows]
		c=1
		for duplicate_index in duplicate_indices:
			duplicate_position=cols.index(duplicate_index)
			##I can't find a different way to do this
			pv=eval(f'pv.assign(duplicate_col_{c}=pv[duplicate_index])')
			cols[duplicate_position]=f'duplicate_col_{c}'
			c+=1
		
		#if we are binning, then rows should only have one varname
		#and that var should be numeric
		if binsize is not None:
			rows=rows[0]
			binsize=int(binsize)
			pv[rows]=pv[rows].astype('int')
			binvar_min=pv[rows].min()
			binvar_max=pv[rows].max()
			binvar_ints=list(range(int(binvar_min),int(binvar_max)+1))
			if binvar_max-binvar_min <=binsize:
				nbins=1
			else:
				nbins=int((binvar_max-binvar_min)/binsize)+1
			
			bin_tuples=[]
			for nbin in range(nbins):
				nbinmin=binvar_min+(binsize*nbin)
				nbinmax=binvar_min+(binsize*(nbin+1))-1
				if nbinmax>=binvar_max:
					nbinmax=binvar_max
				thisbin=(nbinmin,nbinmax)
				bin_tuples.append(thisbin)
				
			bins=pd.IntervalIndex.from_tuples(bin_tuples,closed='both')
			
			if binsize==1:
				binlabels=[i[0] for i in bin_tuples]
				pv=pv.assign(row_bins=pd.cut(df[rows],bins,labels=binlabels,include_lowest=True))
			else:
				pv=pv.assign(row_bins=pd.cut(df[rows],bins,include_lowest=True))
			pv=pv[cols+vals+['row_bins']]
			pv.rename(columns={"row_bins": rows})
			pv['row_bins']=pv['row_bins'].astype('str')
			pv['row_bins']=pv['row_bins'].apply(interval_to_str)
			rows='row_bins'
		#pivot
		
		
		if len(vals)==1:
			vals=vals[0]
			split_cells=False
		else:
			split_cells=True
		
		margins_name='Totals'
		
		pv=pv.pivot_table(
			columns=cols,
			index=rows,
			values=vals,
			aggfunc="sum",
			margins=True,
			margins_name=margins_name
		)
		
		#if we're doing split cells
		#pandas puts the values on top -- flip it to get split cells
		if split_cells:
			cl=len(cols)
			if cl==1:
				pv=pv.swaplevel(0,len(cols),axis=1).sort_index(axis=1)
			elif cl==2:
				#there's got. to be. a better. way.
				pv=pv.swaplevel(0,1,axis=1).sort_index(axis=1)
				pv=pv.swaplevel(1,2,axis=1).sort_index(axis=1)
			colnames_list=pv.columns.tolist()
			
			if len(colnames_list[0])==2:
				all_column_embark_position=colnames_list.index((margins_name,'embarked_slaves'))
				del(colnames_list[all_column_embark_position])
				colnames_list.append((margins_name, 'embarked_slaves'))
				all_column_disembark_position=colnames_list.index((margins_name, 'disembarked_slaves'))
				del(colnames_list[all_column_disembark_position])
				colnames_list.append((margins_name, 'disembarked_slaves'))
			elif len(colnames_list[0])==3:
				all_column_embark_position=colnames_list.index((margins_name,'','embarked_slaves'))
				del(colnames_list[all_column_embark_position])
				colnames_list.append((margins_name, '','embarked_slaves'))
				all_column_disembark_position=colnames_list.index((margins_name,'' ,'disembarked_slaves'))
				del(colnames_list[all_column_disembark_position])
				colnames_list.append((margins_name,'', 'disembarked_slaves'))
			pv=pv[colnames_list]
		
# 		print(pv.index)
# 		print("-->",len(pv.index.names))
		if len(pv.index.names)==1:
			pv=pv.rename_axis(None,axis=0)
		elif len(pv.index.names)==2:
			pv=pv.rename_axis((None,None),axis=0)
# 		pv=pv.rename_axis(None,axis=0)

# 		pv=pv.fillna(0)
# 		pv=pv.style.format("{:,.0f}")
		if mode=='html':
			s=pv.style.format(precision=0, na_rep='0', thousands=",")
			s=s.set_table_styles(
				[
					{"selector": "", "props": [("border", "1px solid grey")]},
					{"selector": "tbody td", "props": [("border", "1px solid grey")]},
					{"selector": "th", "props": [("border", "1px solid grey")]}
				]
			)
			s=s.set_table_attributes('class="dataframe",border="1"')
			data=s.to_html(index_names=False)
			data=re.sub("disembarked_slaves","Disembarked",data)
			data=re.sub("embarked_slaves","Embarked",data)
			data=re.sub("disembarkation_region__import_area__name","",data)
			data=re.sub("disembarkation_region__name","",data)
			data=re.sub("embarkation_region__name","",data)
			data=re.sub("nation__name","",data)
			data=re.sub("row_bins","",data)
			data=re.sub("duplicate_col[a-z|0-9|_]+","",data)
		elif mode=='csv':
			data=pv.to_csv()
		
# 		pv.index.name=''
		#index names = false fails after the numeric formatting....?
# 		html=re.sub('\\n\s+','',html)

	#WE NEED TO SEND BACK THE RESPONSE AS A CSV, PROBABLY USING THIS: django.http.response.FileResponse
	return json.dumps(
		{
			"data":data
		}
	)


@app.route('/estimates_timeline/',methods=['POST'])
def estimates_timeline():

	'''
	Implements the pandas groupby function and returns the sparse summary.
	Excellent for bar & pie charts.
	'''
	st=time.time()
	rdata=request.json
	ids=rdata['ids']
	df=estimate_pivot_tables['df']
	cols=['disembarked_slaves','embarked_slaves']
	df2=df[df['id'].isin(ids)]
	ct=df2.groupby('year',group_keys=True)[cols].agg('sum')
	ct=ct.fillna(0)
	resp={'year':list(ct.index)}
	for col in cols:
		resp[col]=list(ct[col])
	return json.dumps(resp)


@app.route('/crosstabs/',methods=['POST'])
def crosstabs():
	
	'''
	Implements the pandas crosstab function and returns the sparse summary.
	Excellent for pivot tables and maps (e.g., Origin/Destination pairs for voyages with summary values for those pairs)
	Is my solution below (raw html) elegant? No.
	Is that the point? No! Consider that the slavevoyages tables
		1. aren't true pivot tables (can't group rows)
		2. don't even work right now (row header is wrong)
	Recommend using something like this to paginate the bulky html: https://jsfiddle.net/u9d1ewsh/
	And other on-page jquery handlers for column sorting, sankey & map popups, column & row collapsing, etc.
	Unfortunately, I haven't figured out how to do this for less than 10MB and 5 seconds if I style the html dump at all
	--> so for now at least it'll have to be on-page jquery indexing?
	'''
	
	st=time.time()
	rdata=request.json
	ids=rdata['ids']
	csv_output=rdata.get('csv_output')
	
	if len(ids)==0:
		return json.dumps({
			'tablestructure': {},
			'data': {},
			'metadata':{
				'total_results_count': 0,
				'offset':0,
				'limit':0
			}
		})

	#a 2ple for groupby_fields to give us rows & columns (maybe expand this later)
	columns=rdata.get('columns')
	rows=rdata.get('rows')
	val=rdata.get('value_field')
	fn=rdata.get('agg_fn')
	limit=rdata.get('limit') or 10
	offset=rdata.get('offset') or 0
	binsize=rdata.get('binsize')
	order_by=rdata.get('order_by')
	if order_by is not None and order_by not in [['Year range'],['-Year range']]:
		
		ascending=True
		order_by=order_by[0]
		if order_by.startswith("-"):
			ascending=False
			order_by=order_by[1:]
		order_by_list=order_by.split('__')
		order_by_list=tuple(order_by_list)
	else:
		if type(order_by)==list:
			if order_by[0].startswith("-"):
				ascending=False
			else:
				ascending=True
		else:
			ascending=False
		order_by_list=(rows,)
	
	if len(order_by_list)==1:
		order_by_list=order_by_list[0]
	
	normalize=rdata.get('normalize')
	if normalize is not None:
		normalize=normalize[0]
	if normalize not in ["columns","index"]:
		normalize=False
	
	df=big_df['df']
	options=big_df['options']
	df=df[df['id'].isin(ids)]
	
	
	def interval_to_str(s):
		s=str(s)
		return re.sub('[\s,]+','-',re.sub('[\[\]]','',s))

	def makestr(s):
		if s is None:
			return "Unknown"
		else:
			return str(s)

	valuetype=options[val]['type']
	
	pandasvaluetypemap={
		'pct':'float',
		'int':'int',
		'str':'object'
	}
	
	pandasvaluetype=pandasvaluetypemap[valuetype]
	
	##TBD --> NEED TO VALIDATE THAT THE ROWS VARIABLE IS
	####1) NUMERIC TO WORK IN THE FIRST PLACE
	####2) A YEAR VAR IN ORDER TO MAKE SENSE TO A HUMAN END-USER
	if binsize is not None:
# 		print("ROWS",rows)
		binrows=rows
# 		print(binrows)
# 		print(df)

		binsize=int(binsize)
# 		print(df)
		df=df.fillna(0)
# 		df=df.dropna(subset=[rows,val])
		df[binrows]=df[binrows].astype('int')
		df=df[~df[binrows].isin([0])]
		binvar_min=df[binrows].min()
		
		#clean up binvar_min?
		binvar_min=binvar_min-binvar_min%binsize
		if binvar_min%10==0:
			binvar_min+=1
		
		
		binvar_max=df[binrows].max()
		binvar_ints=list(range(int(binvar_min),int(binvar_max)+1))
		if binvar_max-binvar_min <=binsize:
			nbins=1
		else:
			nbins=int((binvar_max-binvar_min)/binsize)+1
		
		bin_tuples=[]
		for nbin in range(nbins):
			nbinmin=binvar_min+(binsize*nbin)
			nbinmax=binvar_min+(binsize*(nbin+1))-1
			if nbinmax>=binvar_max:
				nbinmax=binvar_max
			thisbin=(nbinmin,nbinmax)
			bin_tuples.append(thisbin)
		
		bins=pd.IntervalIndex.from_tuples(bin_tuples,closed='both')
		
		df=df.assign(row_bins=pd.cut(df[rows],bins,include_lowest=True))
		df=df[columns+[val]+['row_bins']]
		df.rename(columns={"row_bins": rows})
		df['row_bins']=df['row_bins'].astype('str')
		df[val]=df[val].astype('int')
		df['row_bins']=df['row_bins'].apply(interval_to_str)
		ct=pd.crosstab(
			[df['row_bins']],
			[df[col] for col in columns],
			values=df[val],
			aggfunc=fn,
			margins=True
		)
		ct=ct.fillna(0)
		
		if order_by_list in [rows,"-"+rows]:
			order_by_list='row_bins'
		
	else:
		ct=pd.crosstab(
			df[rows],
			[df[col] for col in columns],
			values=df[val],
			aggfunc=fn,
			normalize=normalize,
			margins=True
		)
		ct.fillna(0)
	
	if len(columns)==1:
		mlctuples=[[i] for i in list(ct.columns)]
	else:
		mlctuples=list(ct.columns)
	
# 	print("TABLE TUPLES",mlctuples)
#
# 	print(order_by_list,type(order_by_list),type(order_by_list)==tuple)
		
	if order_by is not None:
		ct=ct.sort_values(by=order_by_list,ascending=ascending)
	
	
	def makechild(name,isfield=False,columngroupshow=False,key=None,dtype=None):
		if columngroupshow:
			cgsval="open"
		else:
			cgsval="closed"
		if isfield:
			##N.B. "All" is a reserved column name here, for the margins/totals
			### IN OTHER WORDS, NO VALUE FOR A COLUMN IN THE DF CAN BE "ALL"
			if type(key) in [list,tuple]:
				if key[0]=='All':
					key='All'
				else:
# 					key=re.sub('\.','','__'.join(key))
					key='__'.join([
						i if type(i)!=int else "Undefined" for i in key
					])
					
			
			
			child={
				"columnGroupShow":cgsval,
				"headerName":name,
				"field":key,
				"dtype":valuetype
# 				"filter": 'agNumberColumnFilter',
# 				"sort": 'desc'
			}
			
			if dtype is not None:
				child['dtype']=dtype
			
# 			if ascending:
# 				child['sort']='asc'

			if key=='All':
				child['pinned']='right'
		else:
			child={
				"headerName":name,
				"children":[]
			}
		return child
		
	##N.B. "All" is a reserved column name here, for the margins/totals
	### IN OTHER WORDS, NO VALUE FOR A COLUMN IN THE DF CAN BE "ALL"
	def makecolgroups(colgroups,mlct,fullpath):
		k=mlct.pop()
# 		print("k---->",k)
		if k is not None:
			if type(k)==int or k=="nan":
				#this becomes an issue when we're doing year bins
				#because we have to fill in zeroes to avoid a null data issue
				#and so 0 becomes a column
				k="Undefined"

			if len(mlct)>0 and k!= 'All':
				headernames=[cg['headerName'] for cg in colgroups]
				if k not in headernames:
					thiscg=makechild(k,isfield=False)
					colgroups.append(thiscg)
				else:
					thiscg=[cg for cg in colgroups if cg['headerName']==k][0]
				thiscg_idx=colgroups.index(thiscg)
				colgroups[thiscg_idx]['children']=makecolgroups(thiscg['children'],mlct,fullpath)
			elif k=='All':
				##N.B. "All" is a reserved column name here, for the margins/totals
				thiscg=makechild('',isfield=False)
				thisfield=makechild(k,isfield=True,key=fullpath)
# 				print(thisfield,k,fullpath)
				thiscg['children'].append(thisfield)
				colgroups.append(thiscg)
			else:
				thisfield=makechild(k,isfield=True,key=fullpath)
				colgroups.append(thisfield)
		return colgroups
	
	colgroups=[]	
	indexcol_name=rdata.get('rows_label') or ''
	indexcolcg=makechild('',isfield=False)
	indexcolfield=makechild(indexcol_name,isfield=True,key=indexcol_name,dtype="str")
	indexcolfield['pinned']='left'
	indexcolcg['children'].append(indexcolfield)
	colgroups.append(indexcolcg)
	
	for mlct in mlctuples:
	
# 		print("MLCT",mlct)
		l=list(mlct)
		l.reverse()
		colgroups=makecolgroups(colgroups,l,mlct)

	#place undefined col (if it exists) last
	for idx in range(len(colgroups)):
		colgroup=colgroups[idx]
		if colgroup['headerName']=="Undefined":
			del(colgroups[idx])
			colgroups.append(colgroup)
	
		
	
	output_records=[]
	##N.B. "All" is a reserved column name here, for the margins/totals
	### IN OTHER WORDS, NO VALUE FOR A COLUMN IN THE DF CAN BE "ALL"
# 	allcolumns=[re.sub('\.','',"__".join(c)) if c[0]!='All' else 'All' for c in mlctuples]
	allcolumns=["__".join([i if type(i)!=int else "Undefined" for i in c]) if c[0]!='All' else 'All' for c in mlctuples]
	allcolumns.insert(0,indexcol_name)
	ct=ct.fillna(0)
# 	print(ct)
	
	def convertcell(cellval,pandasvaluetype):
		if pandasvaluetype == "float":
			return float(cellval)
		elif pandasvaluetype=="int":
			return int(cellval)
	
	ctshape=ct.shape
	rowcount=ctshape[0]	
	start=offset
	end=min((offset+limit),rowcount-1)
	
	
	
	if csv_output:
			
		chunk = ct.iloc[start:start+end]
		
		margin=None
		#slap the margin row onto paginated results (except the last page)
		if end!=rowcount-1:
			try:
				margin=ct.loc['All']
			except:
				pass
		
		if margin is not None:
			chunk = pd.concat([chunk,margin.to_frame().T], ignore_index=True)
		
		data=chunk.to_csv(encoding='utf-8')
		
		output={
			'data': data,
			'metadata':{
				'total_results_count': rowcount,
				'offset':offset,
				'limit':limit
			}
		}
		
		return output
	
	ct_records=ct.to_records()
#
# 	for output_record in output_records:
# 		print(allcolumns[0],output_record[allcolumns[0]])
# 		if output_record[allcolumns[0]]=="All":
# 			output_records.remove(output_record)
# 			marginrow=output_record
#
#
	indexkey=allcolumns[0]
	for r in range(len(ct_records)):
# 	ct_records[start:end]:
		row=ct_records[r]
# 		print(row)
		for i in range(len(row)):
			if i==0:
				thisrecord={
					allcolumns[i]:(
						convertcell(row[i],pandasvaluetype) if i!=0 else row[i]
					)
					for i in range(len(row))
				}
# 				print("RECORD---->",thisrecord)
				#THIS IS A RATHER UGLY WAY OF ENSURING THAT INDIVIDUAL YEARS DON'T APPEAR AS HYPHEN-SEPARATED REPEATS, LIKE 1900-1900
				indexkeyval=thisrecord[indexkey]
				if binsize==1 and re.match("[0-9]+-[0-9]+",indexkeyval):
					indexkeyval=thisrecord[indexkey]
# 					print("INDEXKEYVAL",indexkeyval)
					indexkeyval_a,indexkeyval_b=str(indexkeyval).split("-")
					if indexkeyval_a==indexkeyval_b:
						thisrecord[indexkey]=indexkeyval_a
# 		print("RECORD INDEX---->",thisrecord[allcolumns[0]])
# 		print("RECORD---->",thisrecord)
		if thisrecord[indexkey]!="All" and (r>=start and r<=end):
			output_records.append(thisrecord)
		elif thisrecord[indexkey]=="All":
			marginrow=thisrecord
	
	try:
		output_records.append(marginrow)
	except:
		pass
	
# 	for output_record in output_records:
# 		print(allcolumns[0],output_record[allcolumns[0]])

# 	for cg in colgroups:
# 		print("CG",cg)


	output={
		'tablestructure': colgroups,
		'data': output_records,
		'metadata':{
			'total_results_count': rowcount,
			'offset':offset,
			'limit':limit
		}
	}
	
	return json.dumps(output)

# 	except:
# 		abort(400)

@app.route('/csv_download/',methods=['POST'])
def csv_download():
	
	'''
	Downloads CSV
	'''
	
	st=time.time()
	rdata=request.json
	dfname='big_df'
	df=big_df['df']
	ids=rdata['ids']
	df=df[df['id'].isin(ids)]
	# Dataset supports internal filtering; keep the public CSV column contract.
	df=df.drop(columns=['dataset'],errors='ignore')
	df=df.set_index('id')
	df=df.reindex(ids)
	df=df.fillna(0)
	colswitchdict={
		k:big_df['variables'][k]['label'] for k in big_df['variables']
		if 'label' in big_df['variables'][k]
	}
	
	df=df.rename(
		columns=colswitchdict
	)

	return df.to_csv(encoding='utf-8',index=False)

	

@app.route('/dataframes/',methods=['POST'])
def dataframes():
	
	'''
	Allows you to select long-format columns of data on any (indexed) selected field.
	Excellent for a data export or any general dataframe use-case.
	'''
	
	try:
		st=time.time()
		rdata=request.json
		dfname='big_df'
		df=big_df['df']
		ids=rdata['ids']
		df2=df[df['id'].isin(ids)]
		columns=list(set(rdata['selected_fields']+['id']))
		df2=df2[[c for c in columns]]
		df3=df2.set_index('id')
		df3=df3.reindex(ids)
		df3=df3.fillna(0)
		j3=df3.to_dict()
	
		return jsonify(j3)
	except:
		abort(400)

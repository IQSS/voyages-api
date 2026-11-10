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

def fetch_columns(endpoint,fields):
	headers={'Authorization':DJANGO_AUTH_KEY,'Content-Type': 'application/json'}
	r=requests.post(
		url=DJANGO_BASE_URL+endpoint,
		headers=headers,
		data=json.dumps({'selected_fields':fields,'filter':[]})
	)
	return json.loads(r.text)

def combine_fields(columns,spec):
	fieldjoin=spec.get('join',": ")
	cleanup=spec.get('re_cleanup')
	combined=None
	for field in spec['fields']:
		col=pd.Series(columns[field],dtype=object)
		present=col.notna()
		if cleanup:
			col[present]=col[present].astype(str).str.replace(
				cleanup['find'],
				cleanup['replace'],
				regex=True,
				flags=cleanup['flags']
			)
		col=col.where(present,"").astype(str)
		combined=col if combined is None else combined+fieldjoin+col
	return combined

def load_long_df(endpoint,variables):
	obj_vars={v:variables[v] for v in variables if variables[v]['type']=="obj"}
	many_vars={v:obj_vars[v] for v in obj_vars if obj_vars[v].get('many')}
	single_vars={v:obj_vars[v] for v in obj_vars if v not in many_vars}
	
	plain_fields=[v for v in variables if v not in obj_vars]
	main_fields=list(dict.fromkeys(
		plain_fields+[f for v in single_vars for f in single_vars[v]['fields']]
	))
	j=fetch_columns(endpoint,main_fields)
	df=pd.DataFrame({f:j[f] for f in plain_fields})
	for varName in variables:
		vartype=variables[varName]['type']
		if vartype in ["int","pct"]:
			df[varName]=pd.to_numeric(df[varName])
	
	for v in obj_vars:
		spec=obj_vars[v]
		if v in single_vars:
			df[v]=combine_fields(j,spec).values
		else:
			jm=fetch_columns(endpoint,["id"]+spec['fields'])
			ids=pd.Series(jm["id"])
			rolled=combine_fields(jm,spec).groupby(ids.values,sort=False).agg('|'.join)
			df[v]=df['id'].map(rolled).fillna('nan')
	
	return(df[list(variables)])

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
	rdata=request.json
	ids=rdata['ids']
	columns=rdata.get('columns')
	rows=rdata.get('rows')
	val=rdata.get('value_field')
	fn=rdata.get('agg_fn')
	binsize=rdata.get('binsize')
	order_by=rdata.get('order_by')
	offset=int(rdata.get('offset') or 0)
	limit=rdata.get('limit')
	rows_label=rdata.get('rows_label') or ''
	output_format=rdata.get('format') or 'json'
	legacy_csv=bool(rdata.get('csv_output'))
	normalize=rdata.get('normalize')
	if isinstance(normalize,list):
		normalize=normalize[0] if normalize else None
	if normalize not in ["columns","index"]:
		normalize=False
	
	variables=big_df['options']
	is_float=fn=='mean' or variables[val]['type']=='pct' or bool(normalize)
	column_labels=[variables.get(c,{}).get('label',c) for c in columns]
	
	df=big_df['df']
	df=df[df['id'].isin(ids)]
	
	rowkey=rows
	bin_labels=None
	if binsize is not None and len(df)>0:
		binsize=int(binsize)
		df=df[df[rows].notna() & (df[rows]!=0)]
		if len(df)>0:
			years=df[rows].astype('int')
			binvar_min=years.min()
			binvar_min=binvar_min-binvar_min%binsize
			if binvar_min%10==0:
				binvar_min+=1
			binvar_max=years.max()
			if binvar_max-binvar_min<=binsize:
				nbins=1
			else:
				nbins=int((binvar_max-binvar_min)/binsize)+1
			bin_tuples=[]
			for nbin in range(nbins):
				nbinmin=binvar_min+(binsize*nbin)
				nbinmax=min(binvar_min+(binsize*(nbin+1))-1,binvar_max)
				bin_tuples.append((int(nbinmin),int(nbinmax)))
			bin_labels={
				a:(str(a) if binsize==1 and a==b else f"{a}-{b}")
				for a,b in bin_tuples
			}
			in_range=years>=binvar_min
			df=df[in_range]
			years=years[in_range]
			rowkey='__row_bin__'
			df=df.assign(**{rowkey:binvar_min+((years-binvar_min)//binsize)*binsize})
	
	def as_label(v):
		if isinstance(v,float) and v.is_integer():
			return str(int(v))
		return str(v)
	
	def row_label(v):
		if bin_labels is not None:
			return bin_labels[int(v)]
		return as_label(v)
	
	def cell_values(frame):
		vals=frame.to_numpy(dtype=float)
		if is_float:
			return np.round(vals,4).tolist()
		return np.rint(vals).astype(np.int64).tolist()
	
	if len(df)==0:
		body=None
		totals=None
		col_paths=[]
	else:
		undefined_vars=list(dict.fromkeys(columns+([] if bin_labels is not None else [rows])))
		df=df.assign(**{c:df[c].astype(object).where(df[c].notna() & df[c].ne('nan'),'Undefined') for c in undefined_vars})
		
		ct=pd.crosstab(
			df[rowkey],
			[df[c] for c in columns],
			values=df[val],
			aggfunc=fn,
			normalize=normalize,
			margins=True
		).fillna(0)
		
		def undefined_last(t):
			t=t if isinstance(t,tuple) else (t,)
			return (t[0]=='All',)+tuple((x=='Undefined',str(x)) for x in t)
		ct=ct[sorted(ct.columns,key=undefined_last)]
		if bin_labels is None:
			ct=ct.loc[sorted(ct.index,key=lambda i:(i=='All',i=='Undefined'))]
		
		col_tuples=[c if isinstance(c,tuple) else (c,) for c in ct.columns]
		col_paths=[
			['All'] if t[0]=='All' else [as_label(x) for x in t]
			for t in col_tuples
		]
		col_lookup={"__".join(p):c for p,c in zip(col_paths,ct.columns)}
		
		totals=ct.loc['All'] if 'All' in ct.index else None
		body=ct.drop(index='All',errors='ignore')
		
		if order_by:
			ob=order_by[0] or ''
			ascending=not ob.startswith('-')
			key=ob[1:] if not ascending else ob
			if key in [rows_label,rows]:
				# Keep missing labels last without comparing strings with numeric rows.
				known=body.drop(index='Undefined',errors='ignore')
				unknown=body.loc[body.index=='Undefined']
				body=pd.concat([known.sort_index(ascending=ascending,kind='mergesort'),unknown])
			elif key in col_lookup:
				body=body.sort_values(by=col_lookup[key],ascending=ascending,kind='mergesort')
	
	total_count=0 if body is None else len(body)
	if body is not None:
		if limit is not None:
			body=body.iloc[offset:offset+int(limit)]
		elif offset:
			body=body.iloc[offset:]
	
	metadata={
		'total_results_count':total_count,
		'offset':offset,
		'limit':limit
	}
	row_labels=[] if body is None else [row_label(i) for i in body.index]
	
	if output_format=='csv' or legacy_csv:
		if body is None:
			csv_text=''
		else:
			nlevels=len(columns)
			table=pd.concat([body,totals.to_frame().T]) if totals is not None else body.copy()
			table.index=row_labels+(['All'] if totals is not None else [])
			table.index.name=rows_label
			table.columns=pd.MultiIndex.from_tuples(
				[tuple(p+['']*(nlevels-len(p))) for p in col_paths],
				names=column_labels
			)
			if is_float:
				table=table.round(4)
			else:
				table=table.round().astype(np.int64)
			csv_text=table.to_csv(encoding='utf-8')
		if legacy_csv and output_format!='csv':
			return json.dumps({'data':csv_text,'metadata':metadata})
		return Response(csv_text,mimetype='text/csv')
	
	output={
		'row_label':rows_label,
		'column_labels':column_labels,
		'value_label':variables[val].get('label',val),
		'columns':col_paths,
		'rows':row_labels,
		'values':[] if body is None else cell_values(body),
		'totals':[] if totals is None else cell_values(totals.to_frame().T)[0],
		'metadata':metadata
	}
	return json.dumps(output)

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

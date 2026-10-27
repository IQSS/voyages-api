import time
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify,send_file, Response
import json
import math
import requests
from localsettings import *
from index_vars import *
from utils import *
import networkx as nx
from networkx_query import search_nodes, search_edges
import re
import pickle
import os
import pandas as pd
from flask.cli import AppGroup
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = Flask(__name__,template_folder='./templates/')
app.config['JSON_SORT_KEYS'] = False
app.config.from_object(__name__)

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
	REQUEST_COUNT.labels('voyages-geo-networks', 'flask', endpoint, method, status).inc()
	REQUEST_LATENCY.labels('voyages-geo-networks', 'flask', endpoint, method).observe(time.perf_counter() - started_at)
	return response


@app.route('/metrics')
def metrics():
	return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

def kickoff():
	print('LOADING GRAPHS')
	for rcname in rcnames:
		for graph_params in registered_caches[rcname]['graph_params']:
			graphname=graph_params['name']
			load_index(rcname,graphname)

pickle_cli = AppGroup('pickle')
@pickle_cli.command('rebuild')
def rebuild_pickles():
	for rcname in rcnames:
		for graph_params in registered_caches[rcname]['graph_params']:
			
			graphname=graph_params['name']
			
			rc=registered_caches[rcname]
			dataframe_endpoint=rc['endpoint']
			if 'graphs' not in rc:
				rc['graphs']={}
			
			picklefilepath=f'{TMP_PATH}/{rcname}__{graphname}.pickle'
			
			graph,oceanic_subgraph_view,graphname=load_graph(dataframe_endpoint,graph_params,rc)
			linklabels=rc['indices']['linklabels']
			nodelabels=rc['indices']['nodelabels']
			graph_idx=rc['indices'][graphname]
			pk_var=graph_idx['pk']
			itinerary_vars=graph_idx['itinerary']
			weight_vars=graph_idx['weight']
			graph_index=build_index(
				dataframe_endpoint,
				graph,
				oceanic_subgraph_view,
				pk_var,
				itinerary_vars,
				weight_vars,
				linklabels,
				nodelabels,
				rebuilder_number_of_workers=rebuilder_number_of_workers
			)
			with open(picklefilepath, 'wb') as f:
				pickle.dump(graph_index, f, pickle.HIGHEST_PROTOCOL)
			print(f"PICKLE BUILT: {rcname} -- {graphname}")

app.cli.add_command(pickle_cli)

def load_index(rcname,graphname):
	rc=registered_caches[rcname]
	if 'graphs' not in rc:
		rc['graphs']={}
	picklefilepath=f'{TMP_PATH}/{rcname}__{graphname}.pickle'
	if os.path.exists(picklefilepath):
		with open(picklefilepath, 'rb') as f:
			graph_index = pickle.load(f)
	else:
		print(f"WARNING. MAP PICKLE DOES NOT EXIST: {rcname} -- {graphname}")
		graph_index={
			'nodes':pd.DataFrame.from_records({}),
			'edges':pd.DataFrame.from_records({}),
			'nodesdata':{},
			'edgesdata':{}
		}

	if graphname not in rc['graphs']:
		rc['graphs'][graphname]={'index':graph_index}
	else:	
		rc['graphs'][graphname]['index']=graph_index
# 	print("test node record-->",graph_index['nodes'].loc[[0,2]].to_dict())
# 	print("test edge record-->",graph_index['edges'].loc[[0,2]].to_dict())

#SEE INDEX_VARS.PY FOR THE MAPPINGS OF THE DJANGO API FIELDS TO THE DATA DICTIONARIES USED BY THIS APP
registered_caches={
	'ao_maps':ao_maps,
	'voyage_maps':voyage_maps,
	'estimate_maps':estimate_maps
}

rcnames=list(registered_caches.keys())

if not os.path.exists(TMP_PATH):
	os.makedirs(TMP_PATH)

kickoff()

@app.route('/network_maps/',methods=['POST'])
def network_maps():
	
	'''
	Accepts itineraries of UUID's with weights attached
	Returns weighted and classed nodes and edges
	'''
	
	st=time.time()
	rdata=request.json
	cachename=rdata['cachename']
	graphname=rdata['graphname']
	
	pks=rdata['pks']
	
	nodes=registered_caches[cachename]['graphs'][graphname]['index']['nodes']
	aggedges=registered_caches[cachename]['graphs'][graphname]['index']['edges'].copy()
	nodesdata=registered_caches[cachename]['graphs'][graphname]['index']['nodesdata']
	edgesdata=registered_caches[cachename]['graphs'][graphname]['index']['edgesdata']
	
	aggnodes=nodes[nodes['pk'].isin(pks)].drop(columns=(['pk'])).groupby('id').agg('sum')
	
	finalnodes=[
		{	
			'id':row_id,
			'data':nodesdata[row_id],
			'weights':{
				'origin':int(row['origin']),
				'embarkation':int(row['embarkation']),
				'disembarkation':int(row['disembarkation']),
				'post_disembarkation':int(row['post-disembarkation'])
			}
		}
		for row_id,row in aggnodes.iterrows()
		if row_id in nodesdata
	]
	
	## HAVE TO DROP EDGES WHERE WEIGHT IS ZERO BEFORE I DO THE BELOW:
	
	aggedges=aggedges[aggedges['weight']>0]
	aggedges=aggedges[aggedges['pk'].isin(pks)]
	
# 	print("unique pks",len(aggedges['pk'].unique()))
	
	aggedges['c1x']=aggedges['c1x']*aggedges['weight']
	aggedges['c2x']=aggedges['c2x']*aggedges['weight']
	aggedges['c1y']=aggedges['c1y']*aggedges['weight']
	aggedges['c2y']=aggedges['c2y']*aggedges['weight']
	
	aggedges=aggedges.drop(columns=(['pk'])).groupby(['source','target']).agg('sum').reset_index()
	
	aggedges['c1x']=aggedges['c1x']/aggedges['weight']
	aggedges['c2x']=aggedges['c2x']/aggedges['weight']
	aggedges['c1y']=aggedges['c1y']/aggedges['weight']
	aggedges['c2y']=aggedges['c2y']/aggedges['weight']
	
	finaledges=[
		{
			'source':row['source'],
			'target':row['target'],
			'weight':row['weight'],
			'controls':[[row['c1x'],row['c1y']],[row['c2x'],row['c2y']]],
			'type':edgesdata['__'.join([str(row['source']),str(row['target'])])]['type']
		} for row_id,row in aggedges.iterrows()
	]
	
# 	for node in finalnodes:
# 		print(node)
	
	return(jsonify({'nodes':finalnodes,'edges':finaledges}))

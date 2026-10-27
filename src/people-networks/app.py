import time
from flask import Flask,jsonify,request,abort,g,Response
import json
import math
import requests
from localsettings import *
from utils import *
import networkx as nx
from networkx_query import search_nodes, search_edges
import re
import time
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
	REQUEST_COUNT.labels('voyages-people-networks', 'flask', endpoint, method, status).inc()
	REQUEST_LATENCY.labels('voyages-people-networks', 'flask', endpoint, method).observe(time.perf_counter() - started_at)
	return response


@app.route('/metrics')
def metrics():
	return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

standoff_base=4
standoff_count=0

st=time.time()
# G=load_graph()
# while True:
# 	failed=False
# 	try:
G=load_graph()
# 	except:
# 		failed=True
# 	if failed:
# 		standoff_time=standoff_base**standoff_count
# 		print("retrying after %d seconds" %(standoff_time))
# 		time.sleep(standoff_time)
# 		standoff_count+=1
# 	else:
# 		break
print("finished building graphs in %d seconds" %int(time.time()-st))


@app.route('/',methods=['POST'])
def network_maps():
	
	'''
	accepts id (database pk) arrays for:
		enslaved
		enslavers
		voyages
		enslavement_relations
	returns nodes and edges with attributes
	we're now giving back 1 hop (but passing through some intermediary nodes (see utils.py))
	'''
# 	print("received",request.json)
	
	nodes_dict={}
	edges_list=[]
	st=time.time()
	
	for nodeclass in ['enslaved','enslavers','voyages','enslavement_relations']:
		node_id_list=request.json.get(nodeclass)
# 		print("fetching",nodeclass)
		if node_id_list is not None:
			node_id_int_list=[int(i) for i in node_id_list]
			gquery=[{"==":[('node_class',),nodeclass]},{":=":[('id',),node_id_int_list]}]
			querynodes=search_nodes(G, {"and":gquery})
			for n in querynodes:
				nodeclass=G.nodes[n]['node_class']
				if nodeclass=='enslaved':
					levels=3
				else:
					levels=2
# 				print("getting node",n)
				nodes_dict,edges_list=add_neighbors(G,nodes_dict,n,edges_list,levels=levels)
# 				nodes_dict,edges=add_predecessors(G,nodes_dict,n,edges)
# 				nodes_dict,edges=add_successors(G,nodes_dict,n,edges)
	
	nodes=[]
	
	for n_id in nodes_dict:
		node_dict={
			'data':{}
		}
		node=nodes_dict[n_id]
		for k in node:
			if k in ['id','node_class','uuid']:
				node_dict[k]=node[k]
			else:
				node_dict['data'][k]=node[k]
		nodes.append(node_dict)
	
	print("elapsed time:",time.time()-st)
	output={
		"nodes":nodes,
		"edges":edges_list
	}

	st=time.time()
	rdata=request.json
	
	return jsonify(output)

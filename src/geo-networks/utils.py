from math import sqrt
import networkx as nx
from localsettings import *
import requests
import json
import pandas as pd
from networkx_query import search_nodes, search_edges
from maps import rnconversion
import multiprocessing
import numpy as np
import time
import re

def fuzzyplacenamestrip(name):
	name=re.sub("(,\s*port unspecified)|(,\s*unspecified)|(\(colony unspecified\))|(,\s*place unspecified)","",name,re.I)
	return name

def load_graph(endpoint,graph_params,rc):
	graphname=graph_params['name']
	print("loading network:",graphname)
	headers={'Authorization':DJANGO_AUTH_KEY}
	G=nx.DiGraph()
	if rc['type']=='oceanic':
		# FIRST, ADD THE OCEANIC NETWORK FROM THE APPROPRIATE JSON FLATFILE
		## AS POINTED TO IN THE INDEX_VARS.PY FILE
		oceanic_network_file=rc['oceanic_network_file']
		oceanic_network=rnconversion.main(oceanic_network_file)
		G,max_node_id=add_oceanic_network(G,oceanic_network,init_node_id=0)
		print("created oceanic network",G)
		# THEN ITERATE OVER THE GEO VARS IN THE INDEX
		## AND ADD THE RESULTING UNIQUE NODES TO THE NETWORK
		filter_obj=rc['filter']
		G,max_node_id=add_non_oceanic_nodes(G,endpoint,graph_params,filter_obj,init_node_id=max_node_id+1)
		print("added non-oceanic network nodes")
		#then link across the ordered node classes
		ordered_node_classes=graph_params['ordered_node_classes']
		prev_tag=None
		for ordered_node_class in ordered_node_classes:
			tag=ordered_node_class['tag']
			if 'tag_connections' in ordered_node_class:
				tag_connections=ordered_node_class['tag_connections']
				G=connect_to_tags(G,tag,tag_connections)
		print("connected all remaining network edges (non-oceanic --> (non-oceanic & oceanic)) following index_vars.py file ruleset")
		def oceanic_edge_filter(s,t):
			edgetags=G[s][t].get("tags")
			if "oceanic_leg" in edgetags or "embarkation_to_onramp" in edgetags or "offramp_to_disembarkation" in edgetags:
				return True
			else:
				return False

		oceanic_subgraph_view=nx.subgraph_view(G,filter_edge=oceanic_edge_filter)
	return G,oceanic_subgraph_view,graphname


def geteuclideandistance(Ay,Ax,By,Bx):
	distance=sqrt(
		(Ay-By)**2 +
		(Ax-Bx)**2
	)
	return distance

def connect_to_tags(G,this_tag,tag_connections):
	max_edge_id=max([G.edges[e[0],e[1]]['id'] for e in G.edges])
	print("----------\nthis tag",this_tag)
	print("starting graph state",G)
	e=int(max_edge_id+1)
	for tag_connection in tag_connections:
		connect_tag,as_type,mode=tag_connection
		print("connect tag",this_tag,"to",connect_tag,"as",as_type,"in mode",mode)
		#A node with no attributes keeps sneaking in here...
		for n_id in [n for n in G.nodes if this_tag in G.nodes[n]['tags']]:
			thisnode=G.nodes[n_id]
			comp_node_ids=[
				comp_id for comp_id in G.nodes
				if connect_tag in G.nodes[comp_id]['tags']
			]
			if mode=="closest":
				closest_neighbor,distance=getclosestneighbor(G,n_id,comp_node_ids)
				if as_type=="source":
					concat_tag="_to_".join([this_tag,connect_tag])
					s_id=n_id
					t_id=closest_neighbor
				else:
					s_id=closest_neighbor
					t_id=n_id
					concat_tag="_to_".join([connect_tag,this_tag])
				G.add_edge(s_id,t_id,id=e,distance=distance,tags=[concat_tag])
				e+=1
			elif mode=="all":
				for comp_node_id in comp_node_ids:
					distance=get_geo_edge_distance(n_id,comp_node_id,G)
					if as_type=="source":
						concat_tag="_to_".join([this_tag,connect_tag])
						s_id=n_id
						t_id=comp_node_id
					else:
						concat_tag="_to_".join([connect_tag,this_tag])
						s_id=comp_node_id
						t_id=n_id
					G.add_edge(s_id,t_id,id=e,distance=distance,tags=[concat_tag])
					e+=1		
	print("ending graph state",G)
	print("-------------")
	return G

def add_non_oceanic_nodes(G,endpoint,graph_params,filter_obj,init_node_id=0):
	graph_name=graph_params['name']
	node_id=init_node_id
	headers={'Authorization':DJANGO_AUTH_KEY,'Content-Type': 'application/json'}
	ordered_node_classes=graph_params['ordered_node_classes']
	prev_tag=None
	for ordered_node_class in ordered_node_classes:
		## OCEANIC SUBGRAPH COMES FROM A FLATFILE
		tag=ordered_node_class['tag']
		if tag != 'oceanic_waypoint':
			# ON THIS GRAPH, SAY, TRANSATLANTIC REGIONAL ROUTES:
			## WE WANT TO GET EACH GEOGRAPHIC NODE'S VALUES
			## AND APPLY ITS TAG, SAY, EMBARK OR DISEMBARK
			thisgraphvl=ordered_node_class['values']
			thisgraphtag=ordered_node_class['tag']
			att_names=[a for a in list(thisgraphvl.keys()) if thisgraphvl[a] is not None]
			vl_var_names=[thisgraphvl[a] for a in att_names]
			payload={'selected_fields':vl_var_names}
			
			## MAKE SURE YOU APPLY THE FILTER TO THE QUERY
			### E.G., ARE WE AFTER TRANSATLANTIC OR INTRA-AMERICAN VOYAGES?
			payload['filter']=[]
			for f in filter_obj:
				payload['filter'][f]=filter_obj[f]
			
			## MAKE A DATAFRAME CALL ON ALL THE VARIABLES ENUMERATED FOR THIS NODE
			r=requests.post(
				url=DJANGO_BASE_URL+endpoint,
				headers=headers,
				data=json.dumps(payload)
			)
			## TRANSFORM THE RESPONSE INTO ROWS AND DEDUPE
			results=json.loads(r.text)
			rows=[]
			for i in range(len(results[vl_var_names[0]])):
				row=[]
				for vl_var_name in vl_var_names:
					row.append(results[vl_var_name][i])
				if row not in rows:
					rows.append(row)
			## PUSH THE UNIQUE NODES (LAT,LONG,UUID,NAME,VALUE...) INTO THE GRAPH
			for row in rows:
				## BUT WE HAVE TO BE CAREFUL AND TAG THE NODES
				### (E.G., DID WE FIND THIS AS AN EMBARKATION OR DISEMBARKATION?)
				### (AND IF IT ALREADY EXISTS, THEN WE WANT TO LAYER THAT NEW TAG IN)
				### RATHER THAN DUPLICATING
				att_dict={att_name:row[att_names.index(att_name)] for att_name in att_names}
				#WE'VE GOT TO SCREEN OUT AND PROPERLY FORMAT NULL LAT & LONGS...
				#SO THIS IS A GEO-ONLY NETWORK FOR NOW...
				if 'lat' in att_dict and 'lon' in att_dict:
					lat=att_dict['lat']
					lon=att_dict['lon']
					if lat is not None and lon is not None:
						if (float(lat) > -.1 and float(lat) < .1) and (float(lon) > -.1 and float(lon) < .1):
							print("BAD NODE-->",att_dict)
						else:
							att_dict['lat']=float(lat)
							att_dict['lon']=float(lon)
							query=[{"==": [(k,), att_dict[k]]} for k in att_dict]
							existing_nodes=[n for n in 
								search_nodes(G, {"and":query})
							]
							if len(existing_nodes)>0:
								thisnodetags=[G.nodes[n] for n in existing_nodes][0]['tags']
								if tag not in thisnodetags:
									thisnodetags.append(tag)
									G.nodes[existing_nodes[0]]['tags']=thisnodetags
							else:
								att_dict['tags']=[tag]
								rowdict=(node_id,att_dict)
								G.add_nodes_from([rowdict])
								node_id+=1
					else:
						print("BAD NODE-->",att_dict)
	return G,node_id

def add_oceanic_network(G,oceanic_network,init_node_id=0):
	nodes=oceanic_network['nodes']
	links=oceanic_network['links']
	n_id=init_node_id
	#add in the nodes
	oceanic_node_ids=[]
	for node in nodes:
		latitude,longitude=node
		lat=float(latitude)
		lon=float(longitude)
		tags=["oceanic_waypoint"]
		G.add_node(n_id,lat=lat,lon=lon,tags=tags,name=None)
		oceanic_node_ids.append(n_id)
		n_id+=1
	e_id=0
	#link them (directionally)
	for link in links:
		s_id,t_id=[int(n) for n in link]
		distance=get_geo_edge_distance(s_id,t_id,G)
		G.add_edge(s_id,t_id,distance=distance,id=e_id,tags=["oceanic_leg"])
		e_id+=1
	#layer in the onramp/offramp tags
	for n_id in oceanic_node_ids:
		ntags=G.nodes[n_id]['tags']
		successors=[o for o in G.successors(n_id)]
		predecessors=[o for o in G.predecessors(n_id)]
		if len(successors)>0:
			ntags.append('onramp')
		if len(predecessors)>0:			
			ntags.append('offramp')
		G.nodes[n_id]['tags']=ntags
	max_node_id=max(oceanic_node_ids)
	return(G,max_node_id)

def get_geo_edge_distance(s_id,t_id,G):
	s=G.nodes[s_id]
	t=G.nodes[t_id]
	s_lat=s['lat']
	s_lon=s['lon']
	t_lat=t['lat']
	t_lon=t['lon']
	distance=geteuclideandistance(s_lat,s_lon,t_lat,t_lon)
	return(distance)

def getclosestneighbor(G,thisnode_id,comp_nodes_ids):
	distances=[
		(
			get_geo_edge_distance(
				thisnode_id,
				t_id,
				G
			)
			,t_id
		)
		for t_id in comp_nodes_ids
	]
	distances=[d for d in distances if d is not None]
	sorted_distances=sorted(distances, key=lambda tup: tup[0])
	closest_neighbor_distance,closest_neighbor_id=sorted_distances[0]
	return closest_neighbor_id,closest_neighbor_distance

def straightab(A,B,ab_id,result):
	midx=(A[0]+B[0])/2
	midy=(A[1]+B[1])/2
	Control=(midx,midy)
	result[ab_id]=[[[A, B], [Control, Control]]]
	isstraight=True
	return result,Control

def curvedab(A,B,C,prev_controlXY,smoothing=0.15):
# 	print("curving-->",A,B,C,prev_controlXY)
	## this function takes 4 xy points (the first [prev] or last [C] being nullable)
	## and returns a control point and a next control point for the AB segment
	## why this way? because splines that look forward and back not just to points
	## but to control points are much, much smoother
# 	print("curving",A,B,C,prev_controlXY)
	overshoot_corrected=False
	if prev_controlXY is None:
		#first edge
		ControlX = B[0] + smoothing*(A[0]-C[0])
		ControlY = B[1] + smoothing*(A[1]-C[1])
		Control=[ControlX,ControlY]
		nextControl=Control
	else:
		#last edge
		lastedge=False
		if C is None:
			C=B
			lastedge=True
		#all tother edges
		prev_ControlX,prev_ControlY=prev_controlXY
		ControlX = A[0]*2 - prev_ControlX
		ControlY = A[1]*2 - prev_ControlY
		next_ControlX = B[0] + smoothing*(A[0]-C[0])
		next_ControlY = B[1] + smoothing*(A[1]-C[1])
		Control=[ControlX,ControlY]
		nextControl=[next_ControlX,next_ControlY]
		
# 		if lastedge:
		#we're getting gross overshoots on our end nodes in some cases (like Annapolis and Madeira)
		#can't quite pin down why
		#so we're going to flatten those down
		dist_A_to_Control=geteuclideandistance(A[1],A[0],Control[1],Control[0])
		dist_A_to_nextControl=geteuclideandistance(A[1],A[0],nextControl[1],nextControl[0])
		dist_A_to_B=geteuclideandistance(A[1],A[0],B[1],B[0])
		mid=[(A[0]+B[0])/2,(A[1]+B[1])/2]
		dist_A_to_mid=geteuclideandistance(A[1],A[0],mid[1],mid[0])
		
		if dist_A_to_B < max([dist_A_to_Control,dist_A_to_nextControl]):
			overshoot_corrected=True
			if dist_A_to_nextControl < dist_A_to_B:
				Control=nextControl
			elif dist_A_to_Control < dist_A_to_B:
				nextControl=Control
			else:
				Control=mid
				nextControl=mid

		
	
	return Control,nextControl,overshoot_corrected
	
def straightab(A,B,ab_id,result):
	midx=(A[0]+B[0])/2
	midy=(A[1]+B[1])/2
	Control=(midx,midy)
	result[ab_id]=[[[A, B], [Control, Control]]]
	isstraight=True
	return result,Control

def retrieve_nodeXY(node):
	nodeX=node['data']['lat']
	nodeY=node['data']['lon']
	return [nodeX,nodeY]

def add_edge_topathdict(edgesdict,edge_id,c1,c2,pathweight):
	s,t=edge_id
	if 'controls' in edgesdict[s][t]:
		edgesdict[s][t]['controls']['c1'].append({
			'control':c1,
			'weight':pathweight
		})
		edgesdict[s][t]['controls']['c2'].append({
			'control':c2,
			'weight':pathweight
		})
	else:
		edgesdict[s][t]['controls']={
			'c1':[{
				'control':c1,
				'weight':pathweight
			}],
			'c2':[{
				'control':c2,
				'weight':pathweight
			}]
		}
	return edgesdict

def getnodefromdict(node_id,nodesdict,G):
	if str(node_id) in nodesdict:
		node=nodesdict[str(node_id)]
	else:
		node=G.nodes[str(node_id)]
		print("failed on",node_id,"data in graph is-->",node)
	return node

def weightedaverage(controlpoints):
	denominator=sum([wxy['weight'] for wxy in controlpoints])
	if denominator!=0:
		numeratorX=sum([wxy['weight']*wxy['control'][0] for wxy in controlpoints])
		numeratorY=sum([wxy['weight']*wxy['control'][1] for wxy in controlpoints])
		finalX=numeratorX/denominator
		finalY=numeratorY/denominator
	else:
		denominator=len(controlpoints)
		numeratorX=sum([denominator*wxy['control'][0] for wxy in controlpoints])
		numeratorY=sum([denominator*wxy['control'][1] for wxy in controlpoints])
		finalX=numeratorX/denominator
		finalY=numeratorY/denominator
	return [finalX,finalY]

def weightedaverage_tuple(controlpoints):
	denominator=sum([wxy['weight'] for wxy in controlpoints])
	if denominator!=0:
		numeratorXa=sum([wxy['weight']*wxy['control'][0][0] for wxy in controlpoints])
		numeratorYa=sum([wxy['weight']*wxy['control'][0][1] for wxy in controlpoints])
		finalXa=numeratorXa/denominator
		finalYa=numeratorYa/denominator
		numeratorXb=sum([wxy['weight']*wxy['control'][1][0] for wxy in controlpoints])
		numeratorYb=sum([wxy['weight']*wxy['control'][1][1] for wxy in controlpoints])
		finalXb=numeratorXb/denominator
		finalYb=numeratorYb/denominator
	else:
		denominator=len(controlpoints)
		numeratorXa=sum([denominator*wxy['control'][0][0] for wxy in controlpoints])
		numeratorYa=sum([denominator*wxy['control'][0][1] for wxy in controlpoints])
		finalXa=numeratorXa/denominator
		finalYa=numeratorYa/denominator
		numeratorXb=sum([denominator*wxy['control'][1][0] for wxy in controlpoints])
		numeratorYb=sum([denominator*wxy['control'][1][1] for wxy in controlpoints])
		finalXb=numeratorXb/denominator
		finalYb=numeratorYb/denominator
	return [[finalXa,finalYa],[finalXb,finalYb]]

overshoots_corrected=[]

def spline_curves(nodes,edges,paths,G):
	for path in paths:
		pathnodes=path['nodes']
		pathweight=path['weight']
		i=0
		if len(pathnodes)>2:
			prev_controlXY=None
			while i<len(pathnodes)-2:
				A=getnodefromdict(pathnodes[i],nodes,G)
				B=getnodefromdict(pathnodes[i+1],nodes,G)
				C=getnodefromdict(pathnodes[i+2],nodes,G)
				A_id=str(A['id'])
				B_id=str(B['id'])
				Axy=retrieve_nodeXY(A)
				Bxy=retrieve_nodeXY(B)
				Cxy=retrieve_nodeXY(C)
				this_control,next_control,overshoot_corrected=curvedab(Axy,Bxy,Cxy,prev_controlXY)
				if overshoot_corrected:
					Aname=A['data'].get('name')
					Bname=B['data'].get('name')
					if Aname not in overshoots_corrected and Bname not in overshoots_corrected:
						print('OVERSHOOT CORRECTED ON',Aname,Bname)
						overshoots_corrected.append(Aname)
						overshoots_corrected.append(Bname)
				edge_id=[A_id,B_id]
				edges=add_edge_topathdict(edges,edge_id,this_control,next_control,pathweight)
				prev_controlXY=next_control
				i+=1
			A=getnodefromdict(pathnodes[i],nodes,G)
			B=getnodefromdict(pathnodes[i+1],nodes,G)
			C=None
			Axy=retrieve_nodeXY(A)
			Bxy=retrieve_nodeXY(B)
			A_id=str(A['id'])
			B_id=str(B['id'])
			this_control,next_control,overshoot_corrected=curvedab(Axy,Bxy,C,prev_controlXY)
			if overshoot_corrected:
				Aname=A['data'].get('name')
				Bname=B['data'].get('name')
				if Aname not in overshoots_corrected and Bname not in overshoots_corrected:
					print('OVERSHOOT CORRECTED ON',Aname,Bname)
					overshoots_corrected.append(Aname)
					overshoots_corrected.append(Bname)

			edge_id=[A_id,B_id]

			edges=add_edge_topathdict(edges,edge_id,this_control,next_control,pathweight)
			
		elif len(pathnodes)==2:
			A=getnodefromdict(pathnodes[0],nodes,G)
			B=getnodefromdict(pathnodes[1],nodes,G)
			Axy=retrieve_nodeXY(A)
			Bxy=retrieve_nodeXY(B)
			A_id=str(A['id'])
			B_id=str(B['id'])
			midx=(Axy[0]+Bxy[0])/2;
			midy=(Axy[1]+Bxy[1])/2;
			Control=[midx,midy]
			edge_id=[A_id,B_id]
			edges=add_edge_topathdict(edges,edge_id,Control,Control,pathweight)
# 		else:
# 			print("bad path -- only one node?",path)
	
	for s in edges:
		for t in edges[s]:
			controls=edges[s][t]['controls']
			try:
				updatedc1=weightedaverage(controls['c1'])
				updatedc2=weightedaverage(controls['c2'])
				edges[s][t]['controls']=[updatedc1,updatedc2]
			except:
				print("FAILED CURVING",nodes[s],nodes[t],edges[s][t])
	
	return edges

def add_stripped_node_to_dict(graph,n_id,nodesdict):
	node=dict(graph.nodes[n_id])
	if 'uuid' in node:
		#if it has a uuid from the database
		#then its id will be like b3199d76-bf58-40fb-8eeb-be3986df6113
		n_uuid=node['uuid']
	else:
		#else, its id in the nodesdict is the string representation
		#of its id in the networkx graph, which was assigned at service instantiation
		#as an auto-increment
		n_uuid=str(n_id)
	if 'tags' in node:
		node['tags']=None
	nodesdict[n_uuid]['data']=node
	return nodesdict
	

def get_map_data(payload):
	
# 	print(payload)
	
	work_item,pk_var,itinerary_vars,weight_var,graph,nodelabels,linklabels=payload
	
	def oceanic_edge_filter(s,t):
		edgetags=graph[s][t].get("tags")
		if "oceanic_leg" in edgetags or "embarkation_to_onramp" in edgetags or "offramp_to_disembarkation" in edgetags:
			return True
		else:
			return False

	oceanic_subgraph_view=nx.subgraph_view(graph,filter_edge=oceanic_edge_filter)
	pk=work_item[pk_var]
	itinerary=[work_item[iv] for iv in itinerary_vars]
# 	print(itinerary,nodelabels,linklabels)
	if weight_var is not None:
		weight=work_item[weight_var]
		if weight is None:
			weight=0
	else:
		weight=1
	
	uuids=itinerary
	nodesdfrows=[]
	edgesdfrows=[]
	nodesdatadict={}
	edgesdatadict={}

	nodes={uuid:{
		"id":uuid,
		"weights":{
			nl:0 for nl in nodelabels
		},
		"data":{}
		} for uuid in uuids if uuid != None
	}
	
	paths=[]
	edges={}

	# because, for now, the paths are all the same length, N, e.g.
	## people: [origin,embarkation,disembarkation,disposition]
	## voyages: [embarkation,disembarkation]
	# and each (nullable) position in the path carries semantic value
	# to apply the weight of this path across all the affected nodes
	# while retaining that semantic value
	for uuid_idx in range(len(uuids)):
		uuid=uuids[uuid_idx]
		if uuid not in [None,'None']:
			nodelabel=nodelabels[uuid_idx]
			nodes[uuid]['weights'][nodelabel]+=weight
	#similarly for linklabels, which are N-1 long
	abpairs=[(uuids[i],uuids[i+1]) for i in range(len(uuids)-1)]
	thispath={"nodes":[],"weight":weight}

	for apbair_idx in range(len(linklabels)):
		abpair=abpairs[apbair_idx]
		linklabel=linklabels[apbair_idx]
		if "None" in abpair or None in abpair:
			#if we hit a break in the path then we want to reset
			#but still record the discontinuous segments
			if len(thispath['nodes'])>0:
				paths.append(thispath)
				thispath={"nodes":[],"weight":weight}
		else:
			a_uuid,b_uuid=abpair
			amatch=next(iter([n for n in search_nodes(graph,{"==":["uuid",a_uuid]})]),None)
			bmatch=next(iter([n for n in search_nodes(graph,{"==":["uuid",b_uuid]})]),None)
			#the db can still return path node uuid's for places that don't have good geo data (nulled or zeroed lat/long)
			#so we have to screen those out, as they have been excluded from the networkx graph db
			if amatch is not None and bmatch is not None:
				a_id=amatch
				b_id=bmatch
				nodes=add_stripped_node_to_dict(graph,a_id,nodes)
				nodes=add_stripped_node_to_dict(graph,b_id,nodes)
			
				#get the shortest path from a to b, according to the graph
			
				#but also handle transportation self-loops...
				spfail=False
				selfloop=False
				
				if a_id==b_id and linklabel=='transportation':
					#transportation self-loop
					selfloop=True
					successor_ids=[
						n_id for n_id in oceanic_subgraph_view.successors(a_id)
						if 'onramp' in oceanic_subgraph_view.nodes[n_id]['tags']
					]
					if len(successor_ids)==0:
						spfail=True
					else:
						successor_id=successor_ids[0]
				else:
					selfloop=False
			
				if not spfail:
					try:
						if selfloop:
							if linklabel=='transportation':
								sp=nx.shortest_path(oceanic_subgraph_view,successor_id,b_id,'distance')
								sp.insert(0,a_id)
							else:
								sp=nx.shortest_path(graph,successor_id,b_id,'distance')
								sp.insert(0,a_id)
						else:
							if linklabel=='transportation':
								sp=nx.shortest_path(oceanic_subgraph_view,a_id,b_id,'distance')
							else:
								sp=nx.shortest_path(graph,a_id,b_id,'distance')
					except:
						spfail=True

			
				## We need to do one last check here
				## Because there are many routes that can be taken in the network
				## And because many of these are taken
				## This means we can end up with cases where
				## The "shortest path" for this itinerary gets routed through
				## important geographic nodes that aren't actually in the itinerary
				## Yikes. We need to flag that as an error and draw a straight line
				## So that the editors know to update the map network
				if not spfail:
					sp_export_preflight=[graph.nodes[x]['uuid'] if 'uuid' in graph.nodes[x] else x for x in list(sp)]
					for i in sp_export_preflight:
						if type(i)==str and i not in uuids:
							spfail=True

			
				#if all our shortest path work has failed, then return a straight line
				## but log it!
				## OCT. 18 2023: I've found that when paths are NOT provided, this process slows down dramatically.
				## AND RESOLVED THE ISSUE THAT WAS LEADING TO THE OCEANIC NETWORK BEING SKIPPED
				## I USED THE SUBGRAPH VIEW TO FIX THIS PROBLEM -- WE WERE GETTING PATHS LIKE
				## EMBARKATION TO ONRAMP TO A CLOSE DISEMBARKATION NODE TO THE ACTUAL DISEMBARKATION NODE BECAUSE IT HAD A POST-DISEMBARK IN IT. OY...
				if spfail:
					sp=[a_id,b_id]
					print("---\nNO PATH")
					print("from",amatch,graph.nodes[amatch])
					print("to",bmatch,graph.nodes[bmatch]," -- drawing straight line.\n---")
				
			
				#retrieve the uuid's where applicable
				sp_export=[graph.nodes[x]['uuid'] if 'uuid' in graph.nodes[x] else x for x in list(sp)]
			
				#update the full path with this a, ... , b walk we've just performed
				#after trimming the first entry in this walk ** if this is not our first walk
				#otherwise, we get overlaps / false self-loops in our path
				#this crops up in paths that are more than 1 hop long
				if len(thispath['nodes'])>0:
					if thispath['nodes'][-1]==sp_export[0]:
						thispath['nodes']+=sp_export[1:]
				else:
					thispath['nodes']+=sp_export
			
				#update the nodes dictionary with any new nodes
				node_errors=False
				badnodes=[]
				for i in range(len(sp_export)):
					n_id=sp[i]
					uuid=sp_export[i]
					if uuid not in nodes:
						if n_id in graph.nodes:
							newnode_data=dict(graph.nodes[n_id])
							nodes[str(uuid)]={
								'data':newnode_data,
								'id':uuid,
								'weights':{nl:0 for nl in nodelabels}
							}
						else:
							node_errors=True
							badnodes.append(n_id)
				#update the edges dictionary with this a, ..., b walk data
			
				if node_errors:
					print("failed on path-->",sp_export,"specifically on-->",badnodes)
				else:
					sp_DC_pairs=[(sp_export[i],sp_export[i+1]) for i in range(len(sp_export)-1)]
					for sp_DC_pair in sp_DC_pairs:
						s,t=[str(i) for i in sp_DC_pair]
						if s not in edges:
							edges[s]={t:{
								'weight':weight,
								'type':linklabel,
								'source':s,
								'target':t
							}}
						elif t not in edges[s]:
							edges[s][t]={
								'weight':weight,
								'type':linklabel,
								'source':s,
								'target':t
							}
						else:
							edges[s][t]['weight']+=weight
	
	if len(thispath['nodes'])>0:
		paths.append(thispath)
		thispath={"nodes":[],"weight":weight}
	splined=True
	if splined:
		edges=spline_curves(nodes,edges,paths,graph)
	
	for n_id in nodes:
		node=nodes[n_id]
		if node['data']!={}:
			nodesdatadict[n_id]=node['data']
				
		dfrow={}
		dfrow['pk']=pk
		dfrow['id']=n_id
		origin=node['weights'].get('origin')
		embarkation=node['weights'].get('embarkation')
		disembarkation=node['weights'].get('disembarkation')
		post_disembarkation=node['weights'].get('post-disembarkation')
		dfrow['origin']=origin
		dfrow['embarkation']=embarkation
		dfrow['disembarkation']=disembarkation
		dfrow['post-disembarkation']=post_disembarkation
		nonnullvalcount=len([dfrow[k] for k in dfrow if dfrow[k] is not None])
		if nonnullvalcount>0:
			nodesdfrows.append(dfrow)

	for s in edges:
		for t in edges[s]:
			edge=edges[s][t]
			dfrow={k:edge[k] for k in ['weight','source','target']}
			controls=edge['controls']
			dfrow['pk']=pk
			dfrow['c1x']=controls[0][0]
			dfrow['c1y']=controls[0][1]
			dfrow['c2x']=controls[1][0]
			dfrow['c2y']=controls[1][1]
			edgesdfrows.append(dfrow)
			edgesdatakey='__'.join([str(s),str(t)])
			if edge['type'] is not None and edge['weight'] is not None:
				edgesdatadict[edgesdatakey]={'type':edge['type'],'weight':edge['weight']}
		
# 	print(nodesdfrows,edgesdfrows,nodesdatadict,edgesdatadict)
	return nodesdfrows,edgesdfrows,nodesdatadict,edgesdatadict
	


def build_index(endpoint,graph,oceanic_subgraph_view,pk_var,itinerary_vars,weight_var,nodelabels,linklabels,rebuilder_number_of_workers=1):
	
	st=time.time()
	headers={'Authorization':DJANGO_AUTH_KEY,'Content-Type': 'application/json'}
	
	if weight_var is not None:
		selected_fields=[pk_var]+itinerary_vars+[weight_var]
	else:
		selected_fields=[pk_var]+itinerary_vars
	
	payload={'selected_fields':selected_fields,'filter':[]}
	
	r=requests.post(
		url=DJANGO_BASE_URL+endpoint,
		headers=headers,
		data=json.dumps(payload)
	)
	
	results=json.loads(r.text)
	
	print(f"ALL RESULTS: {len(results[pk_var])}")
	
	results_pivoted=[[{k:results[k][i] for k in results},pk_var,itinerary_vars,weight_var,graph,linklabels,nodelabels] for i in range(len(results[pk_var]))]
		
	print(f"REBUILDING WITH {rebuilder_number_of_workers} WORKERS")
	
	with multiprocessing.Pool(rebuilder_number_of_workers) as p:
		proc_results=p.map(get_map_data, results_pivoted)
	
	nodesdfrows=[]
	edgesdfrows=[]
	nodesdatadict={}
	edgesdatadict={}
	
	for pr in proc_results:
		nodesdfrow,edgesdfrow,nodesdatadict_partial,edgesdatadict_partial=pr
		nodesdfrows+=nodesdfrow
		edgesdfrows+=edgesdfrow
		for k in nodesdatadict_partial:
			nodesdatadict[k]=nodesdatadict_partial[k]
		for k in edgesdatadict_partial:
			edgesdatadict[k]=edgesdatadict_partial[k]
	
	nodesdf=pd.DataFrame.from_records(nodesdfrows)
	edgesdf=pd.DataFrame.from_records(edgesdfrows)
	
	print('NODES',nodesdf)
	print('EDGES',edgesdf)
	
	print(f"completed network graph in {time.time()-st}")
	
	return {'nodes':nodesdf,'edges':edgesdf,'nodesdata':nodesdatadict,'edgesdata':edgesdatadict}


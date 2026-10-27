from math import sqrt
import networkx as nx
from localsettings import *
import requests
import json
import itertools
from networkx_query import search_nodes, search_edges
import uuid
import time

def add_nodes(G,long_dataframe,selected_fields,node_class):
	output_dict={}
	for row_idx in range(len(long_dataframe[selected_fields[0]])):
		rowdict={}
		for sf in selected_fields:
			rowdict[sf]=long_dataframe[sf][row_idx]
		id=rowdict['id']
		rowdict['node_class']=node_class
		uid=str(uuid.uuid4())
		rowdict['uuid']=uid
		G.add_node(uid, **rowdict)
		output_dict[id]=rowdict
	return output_dict
		
def load_graph():

	G=nx.Graph()

	#GET VOYAGES
	
	selected_fields=[
		'id',
		'voyage_ship__ship_name',
		'voyage_itinerary__imp_principal_place_of_slave_purchase__name',
		'voyage_itinerary__imp_principal_port_slave_dis__name',
		'voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year'
	]
	
	
	url=DJANGO_BASE_URL+'voyage/dataframes/'
	payload={
		"selected_fields":selected_fields,
		'filter':[]
	}
	
	headers={'Authorization':DJANGO_AUTH_KEY,'Content-Type': 'application/json'}
	
	G=nx.Graph()
	
	r=requests.post(
		url=url,
		headers=headers,
		data=json.dumps(payload)
	)
	
	j=json.loads(r.text)
	voyages_dict=add_nodes(G,j,selected_fields,'voyages')
	
	print("WITH VOYAGES--->",G)

	#GET ENSLAVERS
	
	selected_fields=[
		'id',
		'principal_alias'
	]
	
	url=DJANGO_BASE_URL+'past/enslaver/dataframes/'
	payload={
		"selected_fields":selected_fields,
		'filter':[]
	}
	
	r=requests.post(
		url=url,
		headers=headers,
		data=json.dumps(payload)
	)
	
	j=json.loads(r.text)
	enslavers_dict=add_nodes(G,j,selected_fields,'enslavers')
	
	print("WITH ENSLAVERS-->",G)
	
	#GET ENSLAVED
	
	selected_fields=[
		'id',
		'documented_name',
		'age',
		'gender'
	]
	
	url=DJANGO_BASE_URL+'past/enslaved/dataframes/'
	payload={
		"selected_fields":selected_fields,
		'filter':[]
	}
	
	r=requests.post(
		url=url,
		headers=headers,
		data=json.dumps(payload)
	)
	
	j=json.loads(r.text)
	
	enslaved_dict=add_nodes(G,j,selected_fields,'enslaved')
	
	print("WITH ENSLAVED--->",G)
		
	##FINALLY, RELATIONS
	
	selected_fields=[
		'id',
		'voyage__id',
		'relation_type__name',
		'enslaved_in_relation__enslaved__id',
		'relation_enslavers__enslaver_alias__identity__id',
		'relation_enslavers__roles__name'
	]
	
	#482149 relations without roles.
	#517290 relations WITH roles. promising.
	url=DJANGO_BASE_URL+'past/enslavementrelation/dataframes/'
	payload={
		"selected_fields":selected_fields,
		'filter':[]
	}
	
	headers={'Authorization':DJANGO_AUTH_KEY,'Content-Type': 'application/json'}
	
	
	r=requests.post(
		url=url,
		headers=headers,
		data=json.dumps(payload)
	)
	
	relations_dict={}
	
	j=json.loads(r.text)
	
# 	print("RELATIONS COUNT------>",len(j[selected_fields[0]]),"<--------RELATIONS COUNT")
	relations_check=[]
	for row_idx in range(len(j[selected_fields[0]])):
		rowdict={}
		for sf in selected_fields:
			rowdict[sf]=j[sf][row_idx]
			
		relation_id=rowdict['id']
		if rowdict['voyage__id']==135509:
# 			print(rowdict['voyage__id'],"--->",rowdict['enslaved_in_relation__enslaved__id'])
			relations_check.append(relation_id)
		if relation_id not in relations_dict:
			relations_dict[relation_id]=[rowdict]
		else:
			relations_dict[relation_id].append(rowdict)
# 	
# 	relations_check=list(set(relations_check))
# 	for relcheckid in relations_check:
# 		print("-->",relations_dict[relation_id])
	
	relation_types=[]
	
	for relation_id in relations_dict:
		relation_connections=relations_dict[relation_id]
		
		
		
		
		relation_type=relation_connections[0]['relation_type__name']
		voyage_uuids=list(set([voyages_dict[rc['voyage__id']]['uuid'] for rc in relation_connections if rc['voyage__id'] is not None]))
		enslaved_uuids=list(set([enslaved_dict[rc['enslaved_in_relation__enslaved__id']]['uuid'] for rc in relation_connections if rc['enslaved_in_relation__enslaved__id'] is not None]))
		enslaver_uuids=list(set([enslavers_dict[rc['relation_enslavers__enslaver_alias__identity__id']]['uuid'] for rc in relation_connections if rc['relation_enslavers__enslaver_alias__identity__id'] is not None]))
		
# 		if relation_id in relations_check:
# 			print(relation_connections)
		
		enslaved_ids=[rc['enslaved_in_relation__enslaved__id'] for rc in relation_connections]
		printit=False
# 		if 814219 in enslaved_ids:
# 			print(relation_connections)
# 			print(enslaved_dict[814219])
# 			print(relation_type)
# 			printit=True
		##NOT YET HANDLING ENSLAVER ROLES
		if relation_type=="Marriage":
			#enslaver-to-enslaver marriages
			if len(enslaver_uuids)==2:
				alice,bob=enslaver_uuids
				G.add_edge(alice,bob,role_name='Spouse')
			else:
				print("got more or fewer spouses than anticipated-->",enslaver_uuids,relation_connections)
		elif relation_type in ["Transportation","Ownership"]:
			if len(enslaved_uuids)==0:
				#captain & shipowner/investor relations to voyages FOR WHICH THERE ARE NO NAMED ENSLAVED INDIVIDUALS
				
				
				enslaver_roles={}
				for rc in relation_connections:
					enslaver_identity_id=rc['relation_enslavers__enslaver_alias__identity__id']
					if enslaver_identity_id is not None:
						enslaver_uuid=enslavers_dict[enslaver_identity_id]['uuid']
						enslaver_role=rc['relation_enslavers__roles__name']
						if enslaver_role is None:
							enslaver_role="Undefined"

						if enslaver_uuid not in enslaver_roles:
							enslaver_roles[enslaver_uuid]=[enslaver_role]
						else:
							enslaver_roles[enslaver_uuid].append(enslaver_role)
				
				if len(voyage_uuids)==1:
					voyage_uuid=voyage_uuids[0]
					for enslaver_uuid in enslaver_uuids:
						roles=', '.join(list(set(enslaver_roles[enslaver_uuid])))
						G.add_edge(enslaver_uuid,voyage_uuid,role_name=roles)
				else:
					print('got more or fewer voyages than anticipated-->',relation_connections)
			else:
				#enslaved people connected to voyages without enslavers is a thing, apparently.
				#bears looking into!
				enslaver_roles=list(set([rc['relation_enslavers__roles__name'] for rc in relation_connections]))
				
				if printit:
					print(enslaver_roles)
					print(enslaver_uuids)
				
# 				for rc in relation_connections:
# 					if rc['voyage__id']==135509:
# 						print(rc)				
				
				
				if enslaver_uuids ==[]:
					for rc in relation_connections:
# 					
						enslaved_uuid=enslaved_dict[rc['enslaved_in_relation__enslaved__id']]['uuid']
						
						if rc['voyage__id'] is not None:						
							voyage_uuid=voyages_dict[rc['voyage__id']]['uuid']
							G.add_edge(enslaved_uuid,voyage_uuid)
# 						else:
# 							print('NO VOYAGE??',rc)
				else:
					if len(voyage_uuids)>1:
						print("more voyages than we counted on",rc)
					elif len(voyage_uuids)==0:
						pass
# 						print(relations_dict)
					else:
						voyage_uuid=voyage_uuids[0]
						# if we have a single voyage, then we know that we're dealing with 
						## A. 'indirect' enslavers: captains & investors
						## B. 'direct' enslavers: shippers, owners, consignors, etc.
						
						captain_or_investor=False
						
						enslaver_roles={}
						for rc in relation_connections:
# 							if rc['voyage__id']==135509:
# 								print(rc)
	
							enslaver_identity_id=rc['relation_enslavers__enslaver_alias__identity__id']
							enslaver_uuid=enslavers_dict[enslaver_identity_id]['uuid']
							enslaver_role=rc['relation_enslavers__roles__name']
							if enslaver_role in ['Captain','Investor']:
								captain_or_investor=True
							
							if enslaver_role is None:
								enslaver_role="Undefined"
								
							if enslaver_uuid not in enslaver_roles:
								enslaver_roles[enslaver_uuid]=[enslaver_role]
							else:
								enslaver_roles[enslaver_uuid].append(enslaver_role)
						
						if captain_or_investor:
							#A. INDIRECT IS EASY
							for enslaver_uuid in enslaver_roles:
								roles=', '.join(list(set(enslaver_roles[enslaver_uuid])))
								G.add_edge(enslaver_uuid,voyage_uuid,role_name=roles)
							for eduu in enslaved_uuids:
								G.add_edge(eduu,voyage_uuid,role_name="Enslaved")	
						else:
							#B. DIRECT IS DIFFICULT

							rel_uuid=str(uuid.uuid4())
							reldata={
								'uuid':rel_uuid,
								'relation_type__name':relation_type,
								'id':relation_id,
								'node_class':'enslavement_relations'
							}
			
							enslaver_roles={}
							for rc in relation_connections:
								enslaver_uuid=enslavers_dict[rc['relation_enslavers__enslaver_alias__identity__id']]['uuid']
								enslaver_role=rc['relation_enslavers__roles__name']
								if enslaver_role is None:
									enslaver_role="Undefined"

								if enslaver_uuid not in enslaver_roles:
									enslaver_roles[enslaver_uuid]=[enslaver_role]
								else:
									enslaver_roles[enslaver_uuid].append(enslaver_role)
# 							if rc['voyage__id']==135509:
# 								print(rc)
							if len(voyage_uuids)==0:
								for enslaver_uuid in enslaver_roles:
									for eduu in enslaved_uuids:
										roles=', '.join(list(set(enslaver_roles[enslaver_uuid])))
										G.add_edge(enslaver_uuid,eduu,role_name=roles)
							else:
								if printit:
									print("RECORDING ALTERNATIVE")
								G.add_node(rel_uuid, **reldata)
								G.add_edge(rel_uuid,voyage_uuid)
								if enslaver_uuids is not None:
									for enslaver_uuid in enslaver_uuids:
										roles=', '.join(list(set(enslaver_roles[enslaver_uuid])))
										G.add_edge(rel_uuid,enslaver_uuid,role_name=roles)
								if enslaved_uuids is not None:
									for enslaved_uuid in enslaved_uuids:
										G.add_edge(rel_uuid,enslaved_uuid)
				

	print("WITH CONNECTIONS-->",G)
	return (G)



def add_neighbors(G,nodes_dict,n,edges_list,levels=1):
	edges=G.edges(n,data=True)
	selfdata=G.nodes[n]
	if levels>0:
		for edge in edges:
			s,t,edata=edge
			
			if s==n:
				other=t
			else:
				other=s
			otherdata=G.nodes[other]
# 			print(s,t,otherdata)
			other_node_class=otherdata['node_class']
			if other_node_class=='enslavement_relations':
				nodes_dict,edges_list=add_neighbors(G,nodes_dict,other,edges_list,levels=levels)
			else:
				nodes_dict,edges_list=add_neighbors(G,nodes_dict,other,edges_list,levels=levels-1)
			s,t=sorted([s,t])
			e={'source':s,'target':t,'data':edata}
			if e not in edges_list:
				edges_list.append(e)
			nodes_dict[other]=otherdata
	nodes_dict[n]=selfdata
	return(nodes_dict,edges_list)
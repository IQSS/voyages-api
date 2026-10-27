import requests
import json
from django.core.management.base import BaseCommand, CommandError
import time
import os
from geo.models import *
from voyage.models import *
from voyages3.settings import STATIC_ROOT
import bezier
import numpy as np
import math


'''
Building this for the Guardian.
Walks through all our port-to-port connections and exports a geojson featurecollection
1. points -> a keyed list of all those ports with their names & lat/longs
2. routes -> source:target:linestring
'''

def geteuclideandistance(A,B):
	
	Ax,Ay=A
	Bx,By=B
	
	ed=math.sqrt((Ax-Bx)**2+(Ay-By)**2)
	
	return ed
	


def calControlPoint(points, smoothing=0.15):
	### or {edge_id:[[[Ax,Ay],[Bx,By]],[[ctrl1x,ctrl1y],[ctrl2x,ctrl2y]]]}
	A, B, C=points[:3]
	next_Controlx2 = B[0] + smoothing*(A[0]-C[0])
	next_Controly2 = B[1] + smoothing*(A[1]-C[1])
	
	next_Controlx1 = A[0]*2 - next_Controlx2
	next_Controly1 = A[1]*2 - next_Controly2
	
	Controlx, Controly = next_Controlx2, next_Controly2
# 	print(points)
	result = [[[A, B], [[next_Controlx2, next_Controly2], [next_Controlx2, next_Controly2]]]]
	for i in range(2, len(points)):
# 		print(i)
		if i == len(points)-1:
			start_point, mid_point, end_point = points[i-1], points[i], points[i]
			
			if geteuclideandistance(start_point,mid_point)<3:
				smoothing=0.9
			
		else:
			start_point, mid_point, end_point = points[i-1], points[i], points[i+1]
		next_Controlx1 = start_point[0]*2 - Controlx
		next_Controly1 = start_point[1]*2 - Controly

		next_Controlx2 = mid_point[0] + smoothing*(start_point[0] - end_point[0])
		next_Controly2 = mid_point[1] + smoothing*(start_point[1] - end_point[1])

		result.append([
			[
				start_point,
				mid_point
			],
			[
				[next_Controlx1, next_Controly1],
				[next_Controlx2, next_Controly2]
			]
		])
		Controlx, Controly = next_Controlx2, next_Controly2
	return result




class Command(BaseCommand):
	help = 'rebuilds the options flatfiles'
	def handle(self, *args, **options):
		
		adjacencies=Adjacency.objects.all()
# 		source
# 		target
# 		dataset
# 		distance
		
		voyages=Voyage.objects.all()
		
		voyages_datalist=voyages.values_list(
			"id",
			"voyage_itinerary__imp_principal_place_of_slave_purchase__geo_location__name",
			"voyage_itinerary__imp_principal_place_of_slave_purchase__geo_location__id",
			"voyage_itinerary__imp_principal_place_of_slave_purchase__geo_location__value",
			"voyage_itinerary__imp_principal_port_slave_dis__geo_location__name",
			"voyage_itinerary__imp_principal_port_slave_dis__geo_location__id",
			"voyage_itinerary__imp_principal_port_slave_dis__geo_location__value"
		)
		
		dictkeys=[
			"Voyage ID",
			"Purchase port name",
			"Purchase port PK",
			"Purchase port SPSS code",
			"Disembarkation port name",
			"Disembarkation port PK",
			"Disembarkation port SPSS code"
		]
		
		voyages_dict={}
		
		for v in voyages_datalist:
			
			id=v[0]
			voyages_dict[id]={dictkeys[i]:v[i] for i in range(len(dictkeys))}
			
		d=open("voyages_dict_guardian.json","w")
		d.write(json.dumps(voyages_dict))
		d.close()
			
		
		locations=Location.objects.all()
		
		d=open(os.path.join(STATIC_ROOT,'customcache/routes.json'),'r')
		t=d.read()
		d.close()
		routes=json.loads(t)
		
		datasets=[
			{'name':'transatlantic','code':'0'},
# 			{'name':'intra-american','code':'1'}
		]
		
		featurecollection={"type":"FeatureCollection","features":[]}
		
		geojson_c=0
		c=0
		routes_dict={}
		
		for dataset in datasets:
			dataset_routes=routes[dataset['code']]
			
			for s in dataset_routes:
				
				source=locations.get(pk=int(s))
				
				if source.location_type.name=='Port':
				
					for t in dataset_routes[s]:
					
						route=dataset_routes[s][t]
						target=locations.get(pk=int(t))
# 						if len(route) > 3 and target.name=="Martinique, port unspecified":
# 						if len(route) > 3 and target.id in [3043,3271] and source.id in [3043,3271]:
# 							print(len(route),route)
						startpoint=[float(source.latitude),float(source.longitude)]
				
						feature={
							"type": "Feature",
							"properties": {},
							"geometry": {
								"coordinates": [],
								"type": "LineString"
							}
						}
				
# 						startpoint.reverse()
					
						waypoints=[]
					
						waypoints.append(startpoint)
						
						legidlist=list(route.keys())
						for leg_id in legidlist[1:-1]:
							
# 								if legidlist.index(leg_id) not in [0,len(legidlist)-1]:
							leg=route[leg_id]
							alice,bob=leg[0]
# 							alice.reverse()
# 							bob.reverse()
							waypoints.append(alice)
						
						endpoint=[float(target.latitude),float(target.longitude)]
						
# 						endpoint.reverse()
						
						waypoints.append(endpoint)
						if len(waypoints)>2:
# 							waypoints.reverse()
# 							if source.value==50399 and target.value==60126:
# 								print("gotcha")
# 								
# 								print(waypoints)
# 							for p in waypoints:
# 								print(p)
							
							beziercurves=calControlPoint(waypoints)
							waypoints2=[]
							
							for w in beziercurves:
# 								print(w)
							
								a,b=w[0]
								c1,c2=w[1]
							
								lats=[a[0],c1[0],c2[0],b[0]]
								longs=[a[1],c1[1],c2[1],b[1]]
							
								nodes=np.asfortranarray([lats,longs])
							
								bc=bezier.Curve(nodes,degree=3)
								for i in np.linspace(0,1,20):
									v=bc.evaluate(i)
									waypoints2.append([v[0][0],v[1][0]])
							
							
							thisroute={
								"id":c,
								"source_pk":source.id,
								"source_spss_code":source.value,
								"target_pk":target.id,
								"target_spss_code":target.value,
								"coordinates":waypoints2
							}
							
							
							
							routes_dict[c]=thisroute
							c+=1
							
						
# 							feature['geometry']['coordinates']=waypoints2
# 							
# 							feature['properties']['Target']="%s (%s)" %(source.name,str(source.id))
# 							
# 							feature['properties']['Source']="%s (%s)" %(target.name,str(target.id))
# 							
# 							featurecollection['features'].append(feature)
							
# 							print(source.name,source.value,"--",target.name,target.value)
# 							
# 							if len(featurecollection['features'])>50:
# 								d=open('bezier_geojson_%d.json' %geojson_c,'w')
# 								d.write(json.dumps(featurecollection))
# 								d.close()
# 								geojson_c+=1
# 								featurecollection['features']=[]
# 								print("----->dumped")
# 
# 		d=open('bezier_geojson_%d.json' %geojson_c,'w')
# 		d.write(json.dumps(featurecollection))
# 		d.close()
# 		geojson_c+=1
# 		featurecollection['features']=[]
# 		print("----->dumped")
# 		
		
		d=open('bezier_routes_guardian.json','w')
		d.write(json.dumps(routes_dict))
		d.close()
import re
import json
import sys

'''
converts a legacy voyages routenodes js file to the new json format
'''

def main(inputfname):

	d=open(inputfname,'r')
	t=d.read()
	d.close()
	
	network=json.loads(t)
	
	nodes=network['nodes']
	links=network['links']
	
	js_nodes_strs=[]
	js_links_strs=[]
	
	for node in nodes:
		js_node_str='new L.LatLng(%s, %s)' %(node[0],node[1])
		js_nodes_strs.append(js_node_str)
	
	nodesblock='var routeNodes=[\n\t%s\n]' %(',\n\t'.join(js_nodes_strs))
	
	for link in links:
		js_links_str='{ start: %s, end: %s }' %(link[0],link[1])
		js_links_strs.append(js_links_str)
	
	linksblock='var links=[\n\t%s\n]' %(',\n\t'.join(js_links_strs))
	
	fullblock=';\n'.join([nodesblock,linksblock])
	
	print()
	
	output=fullblock
	return output

if __name__=='__main__':

	fname=sys.argv[1]
	if not fname.endswith('.json'):
		print("fname should end with .json-->",fname)
		exit()

	output=main(fname)
	outputfname=re.sub("\.json$",".js",fname)

	d=open(outputfname,"w")
	d.write(output)
	d.close()


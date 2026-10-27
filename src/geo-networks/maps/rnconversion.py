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

	routenodelines=re.search("routeNodes.*?\[.*?\]",t,re.S).group(0)

	latlngcontents=re.findall("(?<=LatLng\().*?(?=\))",routenodelines)

	latlngs=[]
	for llc in latlngcontents:
		a,b=[float(i.strip()) for i in llc.split(",")]
		latlngs.append([a,b])
	
	# print(latlngs)

	linklines=re.search("links.*?\[.*?\]",t,re.S).group(0)

	linkcontents=re.findall("[0-9]+.*[0-9]+",linklines)

	links=[]
	for lkc in linkcontents:
		a,b=[int(i) for i in re.findall("[0-9]+",lkc)]
		links.append([a,b])

	output={"nodes":[],"links":[]}

	for latlng in latlngs:
		output["nodes"].append([str(i) for i in latlng])
	
	for link in links:
		output["links"].append([str(i) for i in link])

	return output

if __name__=='__main__':

	fname=sys.argv[1]
	if not fname.endswith('.js'):
		print("fname should end with .js-->",fname)
		exit()

	output=main(fname)
	outputfname=re.sub("\.js$",".json",fname)

	d=open(outputfname,"w")
	d.write(json.dumps(output,indent=1))
	d.close()


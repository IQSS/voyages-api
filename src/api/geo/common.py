from .models import *
from django.db.models import Q
#I had hoped to be able to run this as its own api view under the /geo/ endpoint
#However, if we want the geo filter components to only display valid options
#on the basis of what someone has already searched for (e.g., they're looking at Texas
#voyages, or they've selected a particular shipname in autocomplete...)
#then we'll need PAST, VOYAGES, DOCS, BLOG, etc. to be able to apply their filters
#extract the valid spss keys on the field the person is looking for
#and then return a filtered-down tree
def GeoTreeFilter(spss_vals=[],select_all=False):
	'''
		Takes an array of spss vals
		Returns a nested tree of locations
		Ideal for a treeselect js component
		arguments:
			spss_vals --> array of integers, default is []
			select_all --> boolean, default false. If True, the full tree is returned
	'''
	geolocations=Location.objects.all()
	if select_all:
		broadregions=geolocations.filter(location_type__name='Broad Region')
		regions=geolocations.filter(location_type__name='Region')
		places=geolocations.filter(location_type__name='Place')
		
	else:
		broadregions=geolocations.filter(location_type__name='Broad Region')
		broadregions=broadregions.filter(Q(children__children__value__in=spss_vals)|Q(children__value__in=spss_vals)|Q(value__in=spss_vals)).distinct()
		regions=geolocations.filter(location_type__name='Region')
		regions=regions.filter(Q(children__value__in=spss_vals)|Q(value__in=spss_vals)).distinct()
		places=geolocations.filter(location_type__name='Place')
		places=places.filter(value__in=spss_vals).distinct()
	
	locationtree=[]
	
	def locationdict(l):
		ld={
			'id':l.id,
			'name':l.name,
			'longitude':l.longitude,
			'latitude':l.latitude,
			'value':l.value,
			'location_type':{'name':l.location_type.name},
			'spatial_extent':l.spatial_extent
		}
		return ld
	
	for br in broadregions:
		brdict=locationdict(br)
		brdict['children']=[]
		childregions=regions.filter(parent=br)
		for cr in childregions:
			crdict=locationdict(cr)
			childplaces=places.filter(parent=cr)
			crdict['children']=[locationdict(p) for p in childplaces]
			brdict['children'].append(crdict)
		locationtree.append(brdict)
	
	return locationtree
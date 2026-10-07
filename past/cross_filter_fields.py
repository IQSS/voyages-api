'''
	This file defines the filter fields that we will allow in our serializers
	It's used by certain views as well in order to clean up filter requests
	Because I'd like to be able to pass the whole filter object but it's a bit too slow right now
'''

EnslaverBasicFilterVarNames=[
	"aliases__enslaver_relations__relation__voyage__dataset",
	"aliases__enslaver_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__value"
]

EnslavedBasicFilterVarNames=[
	"dataset",
	"enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__name"
]
'''
	This file defines the filter fields that we will allow in our serializers
	It's used by certain views as well in order to clean up filter requests
	Because I'd like to be able to pass the whole filter object but it's a bit too slow right now
'''

VoyageBasicFilterVarNames=[
	"dataset",
	"voyage_itinerary__imp_principal_port_slave_dis__value"
]
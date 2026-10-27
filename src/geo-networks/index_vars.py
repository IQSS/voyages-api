voyage_maps={
	'endpoint':'voyage/dataframes/',
	## THE NAME OF THE INDEX
	'name':'voyage_maps',
	## USE THE VOYAGES SEARCH FILTERS TO ENSURE THAT WE ONLY GET THE OBJECTS WE WANT
	## FOR INSTANCE, ONLY TRANSATLANTIC VOYAGES
	'filter':{},
	## THIS OCEANIC FLAG IS BASICALLY TAKEN FOR GRANTED RIGHT NOW
	## BUT MAYBE LATER ON WE'LL LOAD IN PERSON-TO-PERSON DATA
	'type':'oceanic',
	## STRUCTURE:
	### THE NAME OF THE GRAPH (E.G., PLACE ROUTES)
	### THE NODES, IN ORDER (E.G., ORIGIN, EMBARK, OCEAN, DISEMBARK, POST-DISEMBARK)
	'graph_params': [
		{
			'name':'place',
			'ordered_node_classes':[
				{
					## BECAUSE WE WILL ENCOUNTER SOME NODES IN DIFFERENT CONTEXTS
					### E.G., THE BIGHT OF BIAFRA AS A REGION OF EMBARK & AS DISEMBARK
					### WE WILL WANT TO MAKE SURE THAT WE 
					### SO THAT
					#### A. SUB-GRAPH CALLS WORK PROPERLY
					###### LIKE WHEN WE'RE LINKING ORIGINS TO EMBARKATIONS TO OCEANIC...
					#### B. WE DON'T DUPLICATE, OR TOO AGGRESSIVELY DE-DUPLICATE
					'tag':'embarkation',
					'values':{
						'uuid':'voyage_itinerary__imp_principal_place_of_slave_purchase__uuid',
						'name':'voyage_itinerary__imp_principal_place_of_slave_purchase__name',
						'lat':'voyage_itinerary__imp_principal_place_of_slave_purchase__latitude',
						'lon':'voyage_itinerary__imp_principal_place_of_slave_purchase__longitude',
						'val':'voyage_itinerary__imp_principal_place_of_slave_purchase__value'
					},
					'tag_connections':[
						("onramp","source","closest")
					]
				},
				{
					'tag':'oceanic_waypoint',
				},
				{
					'tag':'disembarkation',
					'values':{
						'uuid':'voyage_itinerary__imp_principal_port_slave_dis__uuid',
						'name':'voyage_itinerary__imp_principal_port_slave_dis__name',
						'lat':'voyage_itinerary__imp_principal_port_slave_dis__latitude',
						'lon':'voyage_itinerary__imp_principal_port_slave_dis__longitude',
						'val':'voyage_itinerary__imp_principal_port_slave_dis__value'
					},
					'tag_connections':[
						("offramp","target","closest")
					]
				}
			]
		},
		{
			'name':'region',
			'ordered_node_classes':[
				{
					'tag':'embarkation',
					'values':{
						'uuid':'voyage_itinerary__imp_principal_region_of_slave_purchase__uuid',
						'name':'voyage_itinerary__imp_principal_region_of_slave_purchase__name',
						'lat':'voyage_itinerary__imp_principal_region_of_slave_purchase__latitude',
						'lon':'voyage_itinerary__imp_principal_region_of_slave_purchase__longitude',
						'val':'voyage_itinerary__imp_principal_region_of_slave_purchase__value'		
					},
					'tag_connections':[
						("onramp","source","closest")
					]
				},
				{
					'tag':'oceanic_waypoint',
				},
				{
					'tag':'disembarkation',
					'values':{
						'uuid':'voyage_itinerary__imp_principal_region_slave_dis__uuid',
						'name':'voyage_itinerary__imp_principal_region_slave_dis__name',
						'lat':'voyage_itinerary__imp_principal_region_slave_dis__latitude',
						'lon':'voyage_itinerary__imp_principal_region_slave_dis__longitude',
						'val':'voyage_itinerary__imp_principal_region_slave_dis__value'		
					},
					'tag_connections':[
						("offramp","target","closest")
					]
				}
			]
		}
	],
	'indices':{
		'place':{
			'pk':'voyage_id',
			'itinerary':[
				'voyage_itinerary__imp_principal_place_of_slave_purchase__uuid',
				'voyage_itinerary__imp_principal_port_slave_dis__uuid'
			],
			'weight':'voyage_slaves_numbers__imp_total_num_slaves_embarked'
		},
		'region':{
			'pk':'voyage_id',
			'itinerary':[
				'voyage_itinerary__imp_principal_region_of_slave_purchase__uuid',
				'voyage_itinerary__imp_principal_region_slave_dis__uuid'
			],
			'weight':'voyage_slaves_numbers__imp_total_num_slaves_embarked'
		},
		'linklabels':['transportation'],
		'nodelabels':[
			'embarkation',
			'disembarkation'
		]
	},
	'oceanic_network_file':'maps/all_routes.js'
}

ao_maps={
	'endpoint':'past/enslaved/dataframes/',
	'name':'african_origins_maps',
	'filter':{},
	'type':'oceanic',
	'graph_params': [
		{
			'name':'place',
			'ordered_node_classes':[
				{
					'tag':'origin',
					'values':{
						'uuid':'language_group__uuid',
						'lat':'language_group__latitude',
						'lon':'language_group__longitude',
						'name':'language_group__name',
						'val':None
					},
					'tag_connections':[
						('embarkation','source','all')
					]
				},
				{
					'tag':'embarkation',
					'values':{
					
						'uuid':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_place_of_slave_purchase__uuid',
						'name':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_place_of_slave_purchase__name',
						'lat':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_place_of_slave_purchase__latitude',
						'lon':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_place_of_slave_purchase__longitude',
						'val':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_place_of_slave_purchase__value'
					},
					'tag_connections':[
						("onramp","source","closest")
					]
				},
				{
					'tag':'oceanic_waypoint',
				},
				{
					'tag':'disembarkation',
					'values':{
						'uuid':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__uuid',
						'name':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__name',
						'lat':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__latitude',
						'lon':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__longitude',
						'val':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__value'
					},
					'tag_connections':[
						("offramp","target","closest")
					]
				},
				{
					'tag':'post-disembarkation',
					'values':{
						'uuid':'post_disembark_location__uuid',
						'val':'post_disembark_location__value',
						'lat':'post_disembark_location__latitude',
						'lon':'post_disembark_location__longitude',
						'name':'post_disembark_location__name'
					},
					'tag_connections':[
						("disembarkation","target","all")
					]
				}
			]
		}
		,
		{
			'name':'region',
			'ordered_node_classes':[
				{
					'tag':'origin',
					'values':{
						'uuid':'language_group__uuid',
						'lat':'language_group__latitude',
						'lon':'language_group__longitude',
						'name':'language_group__name',
						'val':None
					},
					'tag_connections':[
						("embarkation","source","all")
					]
				},
				{
					'tag':'embarkation',
					'values':{
						'uuid':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__uuid',
						'name':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__name',
						'lat':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__latitude',
						'lon':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__longitude',
						'val':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__value'		
					},
					'tag_connections':[
						("onramp","source","closest")
					]
				},
				{
					'tag':'oceanic_waypoint'
				},
				{
					'tag':'disembarkation',
					'values':{
						'uuid':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__uuid',
						'name':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__name',
						'lat':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__latitude',
						'lon':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__longitude',
						'val':'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__value'		
					},
					'tag_connections':[
						("offramp","target","closest")
					]
				},
				{
					'tag':'post-disembarkation',
					'values':{
						'uuid':'post_disembark_location__uuid',
						'val':'post_disembark_location__value',
						'lat':'post_disembark_location__latitude',
						'lon':'post_disembark_location__longitude',
						'name':'post_disembark_location__name'
					},
					'tag_connections':[
						("disembarkation","target","all")
					]
				}
			]
		}
	],
	'indices':{
		'place':{
			'pk':'enslaved_id',
			'itinerary':[
				'language_group__uuid',
				'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_place_of_slave_purchase__uuid',
				'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_port_slave_dis__uuid',
				'post_disembark_location__uuid'
			],
			'weight':None
		},
		'region':{
			'pk':'enslaved_id',
			'itinerary':[
				'language_group__uuid',
				'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_of_slave_purchase__uuid',
				'enslaved_relations__relation__voyage__voyage_itinerary__imp_principal_region_slave_dis__uuid',
				'post_disembark_location__uuid'
			],
			'weight':None
		},
		'linklabels':['origination','transportation','disposition'],
		'nodelabels':[
			'origin',
			'embarkation',
			'disembarkation',
			'post-disembarkation'
		]
	},
	'oceanic_network_file':'maps/ao_routes.js'
}

estimate_maps={
	'endpoint':'assessment/dataframes/',
	## THE NAME OF THE INDEX
	'name':'estimate_maps',
	## USE THE VOYAGES SEARCH FILTERS TO ENSURE THAT WE ONLY GET THE OBJECTS WE WANT
	## FOR INSTANCE, ONLY TRANSATLANTIC VOYAGES
	'filter':{},
	## THIS OCEANIC FLAG IS BASICALLY TAKEN FOR GRANTED RIGHT NOW
	## BUT MAYBE LATER ON WE'LL LOAD IN PERSON-TO-PERSON DATA
	'type':'oceanic',
	## STRUCTURE:
	### THE NAME OF THE GRAPH (E.G., PLACE ROUTES)
	### THE NODES, IN ORDER (E.G., ORIGIN, EMBARK, OCEAN, DISEMBARK, POST-DISEMBARK)
	'graph_params': [
		{
			'name':'region',
			'ordered_node_classes':[
				{
					## BECAUSE WE WILL ENCOUNTER SOME NODES IN DIFFERENT CONTEXTS
					### E.G., THE BIGHT OF BIAFRA AS A REGION OF EMBARK & AS DISEMBARK
					### WE WILL WANT TO MAKE SURE THAT WE 
					### SO THAT
					#### A. SUB-GRAPH CALLS WORK PROPERLY
					###### LIKE WHEN WE'RE LINKING ORIGINS TO EMBARKATIONS TO OCEANIC...
					#### B. WE DON'T DUPLICATE, OR TOO AGGRESSIVELY DE-DUPLICATE
					'tag':'embarkation',
					'values':{
						'uuid':'embarkation_region__name',
						'name':'embarkation_region__name',
						'lat':'embarkation_region__latitude',
						'lon':'embarkation_region__longitude',
						'val':'embarkation_region__name'
					},
					'tag_connections':[
						("onramp","source","closest")
					]
				},
				{
					'tag':'oceanic_waypoint',
				},
				{
					'tag':'disembarkation',
					'values':{
						'uuid':'disembarkation_region__name',
						'name':'disembarkation_region__name',
						'lat':'disembarkation_region__latitude',
						'lon':'disembarkation_region__longitude',
						'val':'disembarkation_region__name'
					},
					'tag_connections':[
						("offramp","target","closest")
					]
				}
			]
		},
		{
			'name':'broad_region',
			'ordered_node_classes':[
				{
					## BECAUSE WE WILL ENCOUNTER SOME NODES IN DIFFERENT CONTEXTS
					### E.G., THE BIGHT OF BIAFRA AS A REGION OF EMBARK & AS DISEMBARK
					### WE WILL WANT TO MAKE SURE THAT WE 
					### SO THAT
					#### A. SUB-GRAPH CALLS WORK PROPERLY
					###### LIKE WHEN WE'RE LINKING ORIGINS TO EMBARKATIONS TO OCEANIC...
					#### B. WE DON'T DUPLICATE, OR TOO AGGRESSIVELY DE-DUPLICATE
					'tag':'embarkation',
					'values':{
						'uuid':'embarkation_region__export_area__name',
						'name':'embarkation_region__export_area__name',
						'lat':'embarkation_region__export_area__latitude',
						'lon':'embarkation_region__export_area__longitude',
						'val':'embarkation_region__export_area__name'
					},
					'tag_connections':[
						("onramp","source","closest")
					]
				},
				{
					'tag':'oceanic_waypoint',
				},
				{
					'tag':'disembarkation',
					'values':{
						'uuid':'disembarkation_region__import_area__name',
						'name':'disembarkation_region__import_area__name',
						'lat':'disembarkation_region__import_area__latitude',
						'lon':'disembarkation_region__import_area__longitude',
						'val':'disembarkation_region__import_area__name'
					},
					'tag_connections':[
						("offramp","target","closest")
					]
				}
			]
		}
	],
	'indices':{
		'region':{
			'pk':'id',
			'itinerary':[
				'embarkation_region__name',
				'disembarkation_region__name'
			],
			'weight':'embarked_slaves'
		},
		'broad_region':{
			'pk':'id',
			'itinerary':[
				'embarkation_region__export_area__name',
				'disembarkation_region__import_area__name'
			],
			'weight':'embarked_slaves'
		},
		'linklabels':['transportation'],
		'nodelabels':[
			'embarkation',
			'disembarkation'
		]
	},
	'oceanic_network_file':'maps/all_routes.js'
}
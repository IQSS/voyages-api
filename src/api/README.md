# SV Django API

The code in this container builds a Python Django API for the SlaveVoyages.org project.

A core principle of the rearchitecture was that the ORM should be exposed so that the relational data could be searched on more or less arbitrarily. For instance, you should be able to search Enslaved People by the name of the ship they were transported on, and you should be able to search Voyages for the names of the Enslaved People transported on them.

## Core dependencies

* The API functionality is built on the Django Rest Framework (DRF) package
* The DRF serializers use drf-writable-nested
	* This allows us to create & edit the highly-relational data
	* But it also necessitates READONLY serializers because it is not performant at scale
	* and that package does not support unique-together constraints
* The more generic api endpoints are documented with Swagger at [{OPEN_API_BASE_URL}/]({OPEN_API_BASE_URL}/)
	* on the basis of the [drf serializes](https://www.django-rest-framework.org/api-guide/serializers/)
	* using the [drf-spectacular package](https://drf-spectacular.readthedocs.io/en/latest/)

If your main concern is to pull a paginated list view of items or a single item by its primary key, read the Django Swagger docs: [{OPEN_API_BASE_URL}/]({OPEN_API_BASE_URL}/)

## Main routes

Each of the project's main object classes has its own route and related endpoints:

* Voyages: [voyage/]({OPEN_API_BASE_URL}/voyage/)
* Enslaved People: [past/enslaved/]({OPEN_API_BASE_URL}/past/enslaved/)
* Enslavers: [past/enslaver/]({OPEN_API_BASE_URL}/past/enslaver/)
* Geographic Locations (presented as a tree): [geo/]({OPEN_API_BASE_URL}/geo/)
* Documents: [docs/]({OPEN_API_BASE_URL}/docs/)
* Blog Posts: [blog/]({OPEN_API_BASE_URL}/blog/)
* Common: [common/]({OPEN_API_BASE_URL}/common/)

The frontend application uses some customized endpoints, which we are still iterating on, in order to provide some highly useful search capabilities. To the extent possible, the methods of using these customized endpoints is kept consistent.

## Schema Presentation

Because we are exposing as much of the ORM as is practicable, it is crucial to be able to inspect what variables are available to us for searching, and what their data types are so that we will know how to search them.

The app uses the Serializers to record in json format the schema for these main object classes, e.g., [{OPEN_API_BASE_URL}/common/schemas/?hierarchical=False&schema_name=Voyage]({OPEN_API_BASE_URL}/common/schemas/?hierarchical=False&schema_name=Voyage) will return a double-underscore-notation representation of the schema for Voyages:

	{
	  "id": {
		"type": "integer",
		"many": false
	  },
	  "voyage_source_connections__id": {
		"type": "integer",
		"many": true
	  },
		...
	  },
	  "voyage_source_connections__source__zotero_grouplibrary_name": {
		"type": "string",
		"many": true
	  }...
	  "voyage_itinerary__imp_principal_region_slave_dis__name": {
		"type": "string",
		"many": true
	  },
	}
  
... and [{OPEN_API_BASE_URL}/common/schemas/?hierarchical=False&schema_name=Voyage]({OPEN_API_BASE_URL}/common/schemas/?hierarchical=False&schema_name=Voyage) will return a nested representation of the schema for Enslaved People:

	{
	  "id": {
		"type": "integer",
		"many": false
	  },
	  "post_disembark_location": {
		"id": {
		  "type": "integer",
		  "many": false
		},
		"uuid": {
		  "type": "number",
		  "many": false
		},
		"name": {
		  "type": "string",
		  "many": false
		},
		"longitude": {
		  "type": "number",
		  "many": false
		}...
	  }...
	}

## Queries on custom endpoints

Requests for data are made via POST calls. In any call, if a django-style double-underscore-notation variable for that endpoint is present as a key in the request body, then its value will be used as a filter.

For instance, if 
```voyage_itinerary__imp_principal_region_slave_dis__name``` is a key in the payload of a call to [{OPEN_API_BASE_URL}/voyage/]({OPEN_API_BASE_URL}/voyage/), then the associated value would be used to filter voyages by the name of their imputed principal region of disembarkation.

Right now, we have 2 basic types of variable, each of which is always handled in the same way -- this will have to change eventually. I don't want to push this too far just yet, because I'm trying to keep *django* in-memory caches out of the picture -- so, for instance, if we wanted to do fuzzy matches on strings, we'd either have to cache those in django or use a solr index *for every text field* or move to a postgresql db which can handle levenstein natively.

### Numeric variables and aggregation views

Numeric variables are filtered according to a min/max range as given by a tuple. A call to voyages with the below payload: 

	{
		'voyage_dates__voyage_began_sparsedate__year':[1820,1850]
	}

Will return voyages that began in the years between 1820-1850 (inclusive).

Use these with aggregation views to make responsive rangesliders. The numeric variables on the different endpoints can all be queried in order to get their min/max.

For instance, a call to ```voyage/aggregations/``` like so:

	{
		'aggregate_fields': [  
			'voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year'
		]
	}

... will return the minimum and maximum values for the years on which voyages arrived at their port of disembarkation. This can be used to make a rangeslider customized for that variable.

### String variables & autocomplete

String variables are filtered according to exact matches in an OR statement. For instance, a call to voyages with the below payload:
	
	{
		voyage_itinerary__imp_principal_region_slave_dis__name : [
			'Barbados',
			'Jamaica'
		]
	}

Will return all the voyages for whom the imputed principal region of disembarkation is either Barbados OR Jamaica.

Use these with autocomplete views to make responsive autocomplete multi-select filter components. This allows for an efficient searching of the text fields with inexact text matches, in order to then subsequently filter on them with an exact OR match.

For instance, a search on [{OPEN_API_BASE_URL}/voyage/autocomplete/]({OPEN_API_BASE_URL}/voyage/autocomplete/) like so:

	{
		voyage_itinerary__imp_principal_region_slave_dis__name : ['jam']
	}
	
...will return: 

	{
		"total_results_count": 1,
		"results": [
			{"id": 71, "label": "Jamaica"}
		]
	}

.... which lets you know that the only valid value in that field that starts with "jam" is "Jamaica" -- from which information you can construct an autocomplete component.

### TBD:

There's work to be done here:

* allow for an inexact match on strings
* allow for a single numeric value to be selected
	* which is only doable if the exact OR filters are no longer the default
* autocomplete views should be paginated

But that will require coordination with the front-end folks, as it will introduce breaking changes.

----------

## Supporting containers

The statistics, mapping, and network endpoints all run in [Python Flask](https://flask.palletsprojects.com/en/3.0.x/) containers that are typically only accessed through the voyages-api Django endpoint.

Flask was chosen because it is even lighter-weight than Django, and so has become a go-to back-end technology for data science webservers.

The typical workflow for these ancillary services is:

* On initialization, the supporting container
	* Runs several dataframe queries against voyages-api
	* Transforms that data and stores it in a networkx or pandas in-memory database
	* Waits for requests from voyages-api
* The supported endpoint (like [voyage/groupby]({OPEN_API_BASE_URL}/voyage/groupby/)) receives
	* A normal filter object
	* One or more extra arguments particular to that endpoint
* The query is run by django, which
	* Retrieves only the pk's for the objects that meet the criteria
	* Passes those pk's and the extra arguments to the external container
* The supporting container then
	* Uses the pk's to filter down what it will be computing on
	* Uses the extra arguments to use Pandas or NetworkX functionality
	* Returns the json-serialized results to voyages-api, which completes the request
	
What follows summarizes how these containers work. Maintainer notes are to come.

### Voyages-Stats

This container uses Pandas to build in-memory databases that can quickly produce json summary statistics that fit well into the plotly.js graphing library. Typically, these requests are about providing summary statistics using pandas functions like groupby.

Right now, we've only applied these statistical operations to the voyages endpoint. We need to have discussions about how we want to visualize numerical data related to people.

### Voyages-People-Networks

This container uses NetworkX to map the numerous connections between people and voyages.

Its development grew out of the fact that the database had to be restructured in order to efficiently represent the *many* many-to-many relations we get in connecting people to people, people to voyages, and peoples' relations to voyages. It was evident that this structural change lent itself to a different representation of the data, even internally. That said, we are not ready to move the full dataset to a graph db, given that voyages should probably stay in a traditional relational db for the foreseeable future.

Its default behavior is to receive an ID for one of its core object classes (an enslaved person, an enslaver, or a voyage), and to return the node with that ID, its neighbors out two hops, and the associated edges.

### Voyages-Geo-Networks

This container uses NetworkX to create essentially a routing system, and then runs every entity for each object class through that routing system, in order to cache, in Pandas, a large dataframe of the various edges and weights for each entity, so that these can be aggregated on, and splined appropriately based on the weights.

----------

## View types

We currently have several more-and-less customized view types which have been, to the greatest extent practicable, applied across the different object classes and their corresponding routes.

### List views

Available for:

* Voyages: {OPEN_API_BASE_URL}/voyage/
* People
	* Enslavers: {OPEN_API_BASE_URL}/past/enslaver/
	* Enslaved People: {OPEN_API_BASE_URL}/past/enslaved/
* Documents: {OPEN_API_BASE_URL}/docs/
* Blog posts: {OPEN_API_BASE_URL}/blog/

These are more or less use generic DRF views. Pagination and ordering are handled like so:

	{
		'results_page': [2],
		'results_per_page': [12]
	}

Yes, I know, I need to get rid of the brackets.

### Dataframe views:

Available for:

* Voyages: {OPEN_API_BASE_URL}/voyage/dataframes/
* Enslaved People: {OPEN_API_BASE_URL}/past/enslaved/dataframes/


#### Dataframe required args

For this endpoint, you only need to specify which fields you want back, using the key ```selected_fields```.

#### Dataframe sample request

You can get long, columnar presentations of data at the dataframe endpoints for voyages, enslaved, and enslavers. For these calls, use the "selected_fields" key:

	{
		'selected_fields': [
			'id',
			'voyage_ship__ship_name',
			'voyage_itinerary__imp_principal_place_of_slave_purchase__name',
			'voyage_itinerary__imp_principal_port_slave_dis__name',
			'voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year'
		]
	}

And you will receive a dictionary whose keys are those variable names and whose values are arrays of equal length containing the corresponding data.

### Statistics views

*N.B. This endpoint relies on the ```voyages-stats``` backend.*

This backend is a supporting Flask container whose principal dependency is Pandas.

Available for:

* Voyages:
	* groupby for all standard data visualizations: {OPEN_API_BASE_URL}/voyage/groupby/
	* crosstabs: {OPEN_API_BASE_URL}/voyage/crosstabs/
	
*Note on crosstabs*: it's is in need of some tweaking to enable pagination. Right now it returns the full [ag-grid crosstab table](https://www.ag-grid.com/javascript-data-grid/column-groups/) (up to 10MB)

*Note on groupby*: it's intended to be used with plotly.js but could easily be used with other visualization packages.

This endpoint enables bar graphs, pie charts, histograms, and so on, by connecting with the ```voyages-stats``` container (see the ```stats``` folder in this repo). It is based on Pandas syntax.

Its workflow is to:

* Apply your query filter (see notes above on our custom filters)
* Retrieve *only the pk's* from the django queryset
* Send those pk's and the required stats arguments to the ```voyages-stats``` backend
* Receive and then return to the user the backend's response

#### Statistics required args

Required arguments for statistics requests:

* ```cachename``` (different caches for different viz's):
	* ```voyage_summary_statistics```
	* ```voyage_pivot_tables```
	* ```voyage_bar_and_donut_charts```
	* ```voyage_xyscatter```
* Others:
	* For ```voyage/groupby``` (see also [Pandas Groupby](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.groupby.html))
		* ```groupby_by``` (rows)
		* ```gropuby_cols``` (cols)
		* ```agg_fn``` (aggregation function, like sum or mean)
	* For ```voyage/crosstabs``` (see also [Pandas CrossTab](https://pandas.pydata.org/docs/reference/api/pandas.crosstab.html))
		* ```rows```
		* ```columns```
		* ```value_field``` (field to aggregate on)
		* ```agg_fn``` (aggregation function, like sum or mean)
		* ```normalize``` (boolean)
		* ```rows_label``` (label for the rows in the crosstabs table)

#### Statistics sample request

To retrieve a bargraph/donut chart-style mix of categorical and numerical variables, you would request, for instance,

* The name of the voyage's region of return (rows)
* The modern tonnage of the ship (cols)
* The aggregation function (sum)
* The cache (```voyage_bar_and_donut_charts```)

Like so: 

	{
		"groupby_by":["voyage_itinerary__region_of_return__name"],
		"groupby_cols":["voyage_ship__tonnage_mod"],
		"agg_fn":["sum"],
		"cachename":["voyage_bar_and_donut_charts"]
	}

And would receive back a 2-key json object, whose keys were the two groupby variables:

	{
		"voyage_itinerary__region_of_return__name": [
			"Antigua",
			"Bahamas",
			"Bahia",
			"Barbados",
			...
		],
		"voyage_ship__tonnage_mod": [
			0.0,
			95.0,
			872.0,
			389.5,
			...
		]
	}

### Maps views

*N.B. This endpoint relies on the ```voyage-geo-networks``` backend.*

This backend is a supporting Flask container whose principal dependencies are NetworkX and Pandas.

Available for:

* Voyages: {OPEN_API_BASE_URL}/voyage/aggroutes/
* Enslaved people: {OPEN_API_BASE_URL}/enslaved/aggroutes/

These requests are handed off to the voyages-geo-networks container.

Its workflow is to:

* Apply your query filter (see notes above on our custom filters)
* Retrieve *only the pk's* from the django queryset
* Send those pk's and the required mapping argument to the ```voyages-geo-networks``` backend
* Receive and then return to the user the backend's response

#### Maps required arg

The only required arg for a map is ```zoomlevel```, which currently only has 2 acceptable values: ```place``` and ```region```. These values correspond to the legacy 3-tiered Voyages geographical schema of ```BroadRegion```, ```Region```, and ```Place```, which (basically) correspond to Continent, Country, and Port.

#### Maps sample request

If a person wanted to map all Trans-Atlantic voyages that are imputed to have landed in Barbados at the ```region``` level, they would request:

	{
		"zoomlevel": ["region"],
		"dataset": [0],
		"voyage_itinerary__imp_principal_region_slave_dis__name" : [
			"Barbados"
		]
	}

And would receive back a json object with 2 keys:

* nodes
	* Have ID's
	* Nodes are multi-classed by weights, for size and styling
		* origin
		* embarkation
		* disembarkation
		* post-disembarkation
	* Their data fields give
		* the location's legacy spss code under 'val'
		* the latitude and longitude
* edges (connecting the nodes)
	* control points to draw bezier curves
	* source and target id's to be keyed against the nodes' id's
	* weights
	* classes/types, mostly used for styling

For instance:

	{
		"edges": [
			{
				"controls": [
					[
						4.760084814385278,
						9.244688671874998
					],
					[
						4.760084814385278,
						9.244688671874998
					]
				],
				"source": "00173d1e-d25c-4190-a839-23da86cbd656",
				"target": "9c9fa53a-8d58-400c-a199-4f2f02cf6e10",
				"type": "origination",
				"weight": 16
			},
			...
		],
		"nodes": [
			{
				"data": {
					"lat": 5.4718,
					"lon": 10.0545,
					"name": "Yemba",
					"uuid": "00173d1e-d25c-4190-a839-23da86cbd656"
				},
				"id": "00173d1e-d25c-4190-a839-23da86cbd656",
				"weights": {
					"disembarkation": 0,
					"embarkation": 0,
					"origin": 18,
					"post-disembarkation": 0
				}
			},
			...
		]
	}

More than enough info. to draw a well-styled map!

#### Network graph views

*N.B. This endpoint relies on the ```voyage-people-networks``` backend.*

This backend is a supporting Flask container whose principal dependency is NetworkX.

Available for:

* Voyages: {OPEN_API_BASE_URL}/voyage/networks/
* Enslaved People and Enslavers: {OPEN_API_BASE_URL}/past/networks/

These requests are handed off to the voyages-people-networks container.

Its workflow is to:

* Apply your query filter (see notes above on our custom filters)
* Retrieve *only the pk's* from the django queryset
* Send those pk's and the required mapping argument to the ```voyages-geo-networks``` backend
* Receive and then return to the user the backend's response

#### Networks required arg

The only required arg for the network endpoints are the pk's for the entities you want to visualize the connections for.

#### Maps sample request

If a person wanted to see who Dee, aged 29 as recorded on voyage 2315 out of Trade Town, they would find the associated pk and request:

	{
		"enslaved":[3]
	}

The other entities are tagged as: ```enslaved```, ```enslavers```, ```voyages```, ```enslavement_relations```.

And would receive back a json object with 2 keys:

* nodes
	* ID and UUID
	* Other relevant metadata (differs between enslavers, enslaved, and voyages)
* edges (connecting the nodes)
	* Source ID
	* Target ID
	* Data (right now, just the role of the enslaver)

For instance:

	{
		"edges": [
			{
				"data": {
					"role_name": "Captain"
				},
				"source": "91a6bf76-1ac7-4c78-9523-c2a83ea6decf",
				"target": "f81d98ab-69aa-44e7-b08d-7d020ddf9970"
			},
			{
				"data": {},
				"source": "91a6bf76-1ac7-4c78-9523-c2a83ea6decf",
				"target": "a9c1989b-4a6a-4ca0-9e45-1c8a41c7cf30"
			},
			...
		]
		"nodes": [
			{
				"id": 1004292,
				"node_class": "enslavers",
				"principal_alias": "García, Juan",
				"uuid": "f81d98ab-69aa-44e7-b08d-7d020ddf9970"
			},
			...
			{
				"age": 28,
				"documented_name": "Dee",
				"gender": 1,
				"id": 3,
				"node_class": "enslaved",
				"uuid": "a9c1989b-4a6a-4ca0-9e45-1c8a41c7cf30"
			},
			...
			{
				"id": 2315,
				"node_class": "voyages",
				"uuid": "91a6bf76-1ac7-4c78-9523-c2a83ea6decf",
				"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year": 1819,
				"voyage_itinerary__imp_principal_place_of_slave_purchase__name": "Trade Town",
				"voyage_itinerary__imp_principal_port_slave_dis__name": "Freetown",
				"voyage_ship__ship_name": "Fabiana"
			}
		]
	}

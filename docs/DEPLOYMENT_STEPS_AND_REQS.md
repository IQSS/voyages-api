# Voyages3 API Deployment Notes

The Voyages3 API project is based on a microservices model. A Django application models the data, manages the database, and processes requests to various endpoints.

In some cases, Django itself retrieves, formats, and returns the requested data. This is usually when the client is requesting full record(s), such as all the data on one more more voyages.

In many cases, however, the data being requested requires aggregation or indexing, based on both legacy and more recent custom functionality. Processing these requests live in Django would either be highly inefficient or require customized algorithms in Django which tend to be memory-inefficient or fragile.

Therefore, for requests such as maps and graphs, Django acts as an API gateway. It receives the client requests, farms these out to dedicated containers (typically written in Flask) that have indexed the API's data, and formats the containers' responses before returning the data to the client.

In order to achieve this, the specialized containers have to index Voyages data when they are instantiated. 

## Container Requirements

These specifications exclude pre-built containers such as:

* MySQL
* Redis
* Mailhog
* Adminer

### geo-networks

Requirements:

* a localsettings file with
	* a ```TMP_PATH``` where large pickle files can be stored
	* a valid key to voyages-api
	* the base URL for the voyages-api endpoints
* a valid mount point at ```TMP_PATH``` for those pickle files to be stored to
* rebuilder_number_of_workers

### stats and people-networks

Requirement: a localsettings file with:

* a valid key to voyages-api
* the base URL for the voyages-api endpoints

### people-networks

Requirement: a localsettings file with:

* a valid key to voyages-api
* the base URL for the voyages-api endpoints

### solr

No special requirements beyond basic solr files which are found in the repo.

### redis

No requirements. Managed by the docker-compose file.

### voyages-api

A localsettings file as specified in ```src/voyages-api/localsettings.py-example```. Key variables in this file that should be changed for deployment are:

* Django's ```SECRET_KEY```
* The settings in ```DATABASES```

#### VOYAGES-API static files

This container also requires, as do most Django projects, a ```static``` directory, mostly for Django plugins' stylesheets and js files.

However, it also requires two folders for custom static objects. Currently, these are located under the ```static``` directory

##### A. Blog images

However, it also requires a folder for static files that cannot be contained in the codebase (though precisely this was historically done in the voyages repo, god help us). Specifically, the blog platform allows users to upload images for use in posts. Currently, this path is set to ```static/uploads/```.

This current configuration (of uploads going to ```static/uploads/```) relies on two settings, currently established in settings.py:

First, the uploads folder's location is set as follows

	# Default FileBrowser site
	site = FileBrowserSite(name='filebrowser')
	site.storage.location = "static"
	site.directory="uploads/"
	site.storage.base_url = "/static/uploads"

Second, of course, the above relies on the static folder being set as: ```STATIC_ROOT='static'```. You'll therefore see below, in the deployment steps, a requirement to create two static folders.

##### B. IIIF Manifests

The document viewer relies on third-party IIIF image servers -- but those servers' image manifests are not up to snuff. We therefore have to generate manifests for our documents that leverage those image servers but use our own metadata.

These manifests currently live in ```static/iiif_manifests```

## Instructions

To deploy the project in a production setting, the following steps should be followed, in order.

### 1. Database dump

Download the latest database dump from the Google Drive project share and
expand into the `data/` directory. Rename the expanded file to `data/voyages_prod.sql`.

Create the MySQL database. Then inject the database dump: ```sudo mysql voyages_api < data/voyages_prod.sql```

### 2. API containers

Build the core service containers (API and Solr).

```bash
local:~/Projects/voyages-api$ docker compose up --build -d voyages-api voyages-adminer voyages-solr voyages-redis
```

Run the app setup and configuration tasks in the below order.

#### 2a. Standard Django management commands:

The below commands should be run on the Django voyages-api container to build out static assets (which Swagger and other plugins use) and to bring the database into sync with any model changes in the codebase.

```bash
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py migrate'
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py collectstatic --noinput'
```

#### 2b. Django static assets:

This project has several custom Django management commands. Only one of these commands must be run to start the project from scratch, and they relate to the deployment of static assets (see the section on ```VOYAGES-API static files``` above).

Currently, those static assets live in folders under ```api/static/```. First, we'll want to make sure those subdirectories exist (I haven't included them in the repo because I don't know if Derek will want to move them out of ```api/static```):

```bash
local:~/Projects/voyages-api$ mkdir -p src/api/static/iiif_manifests/'
local:~/Projects/voyages-api$ mkdir -p src/api/static/uploads/'
```

Then we'll want to regenerate the IIIF manifests (or these can be shared via Google Drive, as they are lightweight and don't change often):

```bash
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py iiif_generate_manifests'
```

And finally, we'll want to populate the uploads folder at ```api/static/uploads``` as these assets are used by the blog. *Those* assets should be shared via Google Drive.

#### 2c. Solr commands:

If you are building from scratch, you will have to create the necessary solr cores:

```
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c voyages -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c enslavers -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c enslaved -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c blog -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c autocomplete_source_titles -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c autocomplete_ship_names -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c autocomplete_enslaved_names -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c autocomplete_enslaver_aliases -d /srv/voyages/solr
```

Then you will want to use those solr cores to build out indexes using the below custom Django management command (this will take approx. 1 minute):

```
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py rebuild_indices'
```

#### 2d. Flask Containers

Build the API component containers.

```bash
local:~/Projects/voyages-api$ docker compose up --build -d voyages-geo-networks voyages-people-networks voyages-stats
```

##### 2d.1 Note on voyages-geo-networks
	
This container relies on highly resource-intensive calculations. In order to be responsive in production, its results must therefore be indexed ahead of time. These indexes are saved as pickles in the ```voyages-geo-network``` container's ```TMP_PATH``` directory, which is ignored by git.

When the container is started, it looks in ```TMP_PATH``` to find these pickle files. It loads those it finds. If any are missing, it generates them and then saves them to ```TMP_PATH``` so they can be used at the next startup.

Obviously, if the database is updated, such as with the addition of new voyages, then this index needs to be updated. The command can therefore be invoked manually, as below:

```bash
local:~/Projects/voyages-api$ docker exec -i voyages-geo-networks bash -c 'flask pickle rebuild'
```

Generating all of the indices can take up to 30 minutes. However, if more cores are added to the container, this indexing process can be multi-threaded by setting the ```rebuilder_number_of_workers``` variable to the number of cores. And yet, outside of this indexing workflow, more than 1 core is overkill for this container, so it would be difficult to realize the value of this innovation without some interesting cloud architecture.

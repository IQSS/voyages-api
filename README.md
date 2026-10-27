# VOYAGES API

The following notes provide an overview of how to install and run the SV API project, which is a restructuring of SlaveVoyages.org to bring it closer to a true microservices model.

For notes on the project structure, see the [Project Structure readme file](src/api/README.md)

For a Swagger UI presentation of the API documentation's generic public endpoints, go to the root url of the endpoint:

* Running locally: [127.0.0.1:8000/](127.0.0.1:8000/)
* Current public location (subject to change): [https://voyages-api-staging.crc.rice.edu/](https://voyages-api-staging.crc.rice.edu/)

## System Requirements

For reference, this document was written while testing on a 2022 MacBook Pro
running MacOS Ventura and Docker Desktop 4.21.1.

Install the macOS Xcode Command Line Tools.

```bash
local:~$ sudo xcodebuild -license
local:~$ xcode-select install
```

Install Homebrew.

```bash
local:~$ /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

Install and configure the GitHub CLI.

```bash
local:~$ brew install gh
local:~$ gh auth login
```

Install Docker Desktop.

Optionally, download and install manually instead of using Homebrew.

```bash
local:~$ brew install --cask docker
```

## Getting Started

Change to your local project directory (in this case, `~/Projects`).

```bash
local:~$ cd Projects
```

Fork the `rice-crc/voyages-api` repository and clone to your local environment.

```bash
local:~/Projects$ gh repo fork rice-crc/voyages-api --remote --default-branch-only --clone
```

## Local App Deployment

Change to the cloned repository directory.

```bash
local:~/Projects$ cd voyages-api
```

Copy the default config files for each app component.

```bash
local:~/Projects/voyages-api$ cp src/api/voyages3/localsettings.py{-default,}
local:~/Projects/voyages-api$ cp src/api/voyages3/google_auth.json{-example,}
local:~/Projects/voyages-api$ cp src/geo-networks/localsettings.py{-default,}
local:~/Projects/voyages-api$ cp src/people-networks/localsettings.py{-default,}
local:~/Projects/voyages-api$ cp src/stats/localsettings.py{-default,}
```

Download the latest database dump from the Google Drive project share and
expand into the `data/` directory. Rename the expanded file to `data/voyages_prod.sql`.

*Optional*: Add the correct credentials to the `src/api/voyages3/google_auth.json` file in order to enable automatic blog translations.

Build the API containers. The component containers must be built separately.

```bash
local:~/Projects/voyages-api$ docker compose up --build -d voyages-mysql voyages-api voyages-adminer voyages-solr
```

_Note: you can remove the `-d` option to run the process in the foreground. JCM always does this to watch the logs._

Allow a short bit of time for the mysql container to initialize. Then inject the sql dump.

```bash
local:~/Projects/voyages-api$ docker exec -i voyages-mysql mysql -uroot -pvoyages voyages_api < data/voyages_prod.sql
```

Verify the data import.

```bash
local:~/Projects/voyages-api$ docker exec -i voyages-mysql mysql -uvoyages -pvoyages -e "show databases"
local:~/Projects/voyages-api$ docker exec -i voyages-mysql mysql -uvoyages -pvoyages -e "show tables from voyages_api"
local:~/Projects/voyages-api$ docker exec -i voyages-mysql mysql -uvoyages -pvoyages -e "select * from voyages_api.voyage_voyage limit 1"
```

Run the app setup and configuration tasks.

```bash
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py collectstatic --noinput'
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py migrate'
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c voyages -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c enslavers -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c enslaved -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c blog -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c sources -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c voyagesources -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c enslaversources -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-solr solr create_core -c enslavedsources -d /srv/voyages/solr
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py index_enslaver_data'
local:~/Projects/voyages-api$ docker exec -i voyages-api bash -c 'python3 manage.py rebuild_indices'
```

Build the API component containers.

```bash
local:~/Projects/voyages-api$ docker compose up --build -d voyages-geo-networks voyages-people-networks voyages-stats
```

Rebuild the map routes (this can take some time).

```bash
local:~/Projects/voyages-api$ docker exec -i voyages-geo-networks bash -c 'flask pickle rebuild'
```

## A note on media files

The API requires certain media or static files to be available, primarily for the blog endpoint. These require the following definitions in the ```localsettings.py``` file:

	STATIC_URL="static/"
	VOYAGES_FRONTEND_BASE_URL="http://127.0.0.1:3000/"
	OPEN_API_BASE_URL="http://127.0.0.1:8000/"

And the following in the ```settings.py``` file:

	STATIC_ROOT='static'
	site = FileBrowserSite(name='filebrowser')
	site.storage.location = STATIC_ROOT
	site.directory="uploads/"
	site.storage.base_url = "/static/uploads"
	site_storage_base_url = site.storage.base_url

### Media files use-case 1: the blog

The blog uses the FileBrowserSite mixin to allow our team to upload content (thumbnail images, content-embedded images, and pdfs linked to from the blog) and use it in blog posts. The settings.py variables discussed above require that the following path exists for those assets to be stored to: ```static/uploads```. Be careful, it's easy to end up with extra or missing slashes.

### Media files use-case 2: IIIF manifests

The document viewer requires our own home-grown manifests. These are uploaded to an S3 bucket, which the frontend then references. The backend will generate these via a manage.py command, but as of june 11, that needs to be updated for this S3 approach.

## Generating an API Key for the Flask Components

The Flask components of the app require an API key.

Create a new Django superuser account through the CLI.

```bash
local:~/Projects/voyages-api$ docker exec -it voyages-api bash -c 'python3 manage.py createsuperuser'
```

Use those credentials to log in to the Django admin interface at
[127.0.0.1:8000/admin/](127.0.0.1:8000/admin/) and create an API
token for the account.

Update the `src/stats/localsettings.py` and `src/networks/localsettings.py` files with
the new token.

Restart the Flask component containers.

```bash
local:~/Projects/voyages-api$ docker restart voyages-geo-networks voyages-people-networks voyages-stats
```

## Cleanup

If you want to tear it down:

```bash
local:~/Projects/voyagesapi$ docker compose down
local:~/Projects/voyagesapi$ docker container prune -f
local:~/Projects/voyagesapi$ docker image prune -f
local:~/Projects/voyagesapi$ docker volume prune -f
local:~/Projects/voyagesapi$ docker network prune -f
```

## Resources

Note the following project resources:

* Voyages API: [127.0.0.1:8000/](127.0.0.1:8000/)
* API Stats Component: [http://127.0.0.1:5000](http://127.0.0.1:5000/)
* API Geo Networks Component: [http://127.0.0.1:5005](http://127.0.0.1:5005/)
* API People Networks Component: [http://127.0.0.1:5006](http://127.0.0.1:5006/)
* Solr: [http://127.0.0.1:8983](http://127.0.0.1:8983)
* Adminer: [http://127.0.0.1:8080](http://127.0.0.1:8080)
* Redis: [http://127.0.0.1:6379](http://127.0.0.1:6379)

## Geo Networks

This container runs NetworkX and Pandas in order to build splined geographic sankey maps that are aggregated in a weighted manner on shared routes.

When initialized for the first time, for voyages and people, at region and place levels (A total of 4 runs):

* Creates a basic geographic network in NetworkX
* Asks the voyages-api component for relevant geo data to flesh the map out
* Then pulls the full itinerary for
  * the class in question (voyages or people)
  * at the resolution in question (regions or places)
* For each of those entities
  * It draws the full, splined path
  * Stores the touched nodes and edges in a dataframe
* At the end of each run, it
  * Loads the full dataframe into memory
  * And dumps the results to a pickle file under /tmp

This can take 15 minutes. When initialized subsequently, it loads the pickles into memory in about 2 seconds.

## Adminer

The Adminer container is provided as an optional way of working with the database.

Visit [http://127.0.0.1:8080](http://127.0.0.1:8080) and log in with the following values.

* Server: voyages-mysql
* User: voyages
* Password: voyages
* Database: voyages-api

## Development Workflow

This project follows a fork-and-pull workflow.

* The `rice-crc:voyages-api` repository is referred to as `upstream` and your fork as `origin`
* The upstream/develop branch serves as the default change integration point between developers
* A developer makes Pull Requests from their origin/working-branch to upstream/develop

Keep the following in mind when contributing code.

* Keep your fork up-to-date with the upstream repository
* Always start new work with a new working branch
* Periodically fetch and rebase the latest upstream/develop changes onto your local working-branch
* Do not make Pull Requests containing untested or unfinished code unless intended for temporary review and discussion
* Clean up the work in your local environment once a Pull Request has been accepted and merged

Use the following git process to contribute work.

```bash
git fetch upstream            # Pull the latest changes from upstream/develop
git checkout -b <short-desc>  # and create a new working branch

git fetch upstream            # Do work; before any commits, pull the latest
git rebase upstream/develop   # changes from upstream/develop and rebase onto
                              # your working branch

git add . && git commit       # Commit your changes to the working branch
                              # Repeat pulling changes and adding commits until
                              # your work is done

git push origin HEAD          # Push the working branch to your fork and make
gh pr create --fill           # a Pull Request to upstream/develop

git checkout develop          # Once the PR is accepted and merged, delete
git branch -D <short-desc>    # your working branch

git pull                      # Pull the latest changes from upstream/develop
git push                      # and update your fork by pushing to origin/develop
```

docker build . -t voyages-api:latest

docker run \
	-v ./static:/srv/voyages-api/static \
	-v ./voyages3/localsettings.py:/srv/voyages-api/voyages3/localsettings.py \
	--name voyages-api \
	-t voyages-api:latest
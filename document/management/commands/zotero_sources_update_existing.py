from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from document.models import Source, Transcription, SourceType,DocSparseDate
from xml.etree import ElementTree
import json
import re
import requests
#adding in authorization and urls from localsettings
from voyages3.localsettings import VOYAGES_FRONTEND_BASE_URL,zotero_credentials
from voyages3.settings import STATIC_ROOT
from pyzotero import zotero

_max_errors = 5 # Maximum number of *consecutive* errors for the APIs we call.
# _voyages_cache_filename = '.cached_voyages_data'
_zotero_cache_filename = f'{STATIC_ROOT}/.cached_zotero_data'

def _makeLabelValue(label, value, lang):
	return { 'label': { lang: [label] }, 'value': { lang: value } }

class Command(BaseCommand):
	help = """\
		Our zotero_sources_update_existing script is insufficiently targeted.\
		This script allows us to focus only on sources that have already been imported \
		from Zotero (rather than pulling down new sources as well), and, even more, to \
		go after sub-collections by providing a shortref to filter on. For instance, \
		running `manage.py update_zotero_sources --shortref="clement"` will update only \
		the 372 (as of Feb 9 2025 sources from Michigan).\
	"""
	
	def add_arguments(self, parser):
		parser.add_argument("--shortref", default=None)

	def handle(self, *args, **options):
		library_id=zotero_credentials['import_from_library_ids']
		library_type=zotero_credentials['library_type']
		api_key=zotero_credentials['api_key']
		zot = zotero.Zotero(library_id, library_type, api_key)
		
		shortref=options['shortref']
		
		sources=Source.objects.all()
		if shortref is not None:
			sources=sources.filter(short_ref__name__icontains=shortref)
			
		print(sources)
		
		c=1
		errors=0
		cutoff=5
		for source in sources:
			print(source)
			zotero_item_id=source.zotero_item_id
			print(zotero_item_id)
# 			while True:
# 				res = requests.get( \
# 				f"https://api.zotero.org/groups/{library_id}/items/{zotero_item_id}?format=json&include=bib&style=chicago-fullnote-bibliography", \
# 				headers={ 'Authorization': f"Bearer {api_key}" }, \
# 				timeout=60)
				
			item=zot.item(zotero_item_id)
				
# 				if res.status_code==200:
# 					break
# 				else:
# 					print("Error",res)
# 					errors+=1
# 					if errors>cutoff:
# 						failure=True
# 						print("SKIPPING",source.title)
		
			if not failure:
				print(item)
				
				exit()
				
				bib=item['bib']
				
				source.bib=bib
				source.save()
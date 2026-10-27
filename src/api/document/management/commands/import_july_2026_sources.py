


from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from document.models import Source, ShortRef,Transcription, SourceType,DocSparseDate,SourceVoyageConnection
from voyage.models import Voyage,VoyageDates
from xml.etree import ElementTree
import json
import re
import requests
#adding in authorization and urls from localsettings
from voyages3.localsettings import VOYAGES_FRONTEND_BASE_URL,zotero_credentials
from voyages3.settings import STATIC_ROOT
from pyzotero.zotero import Zotero
import os

class Command(BaseCommand):

	def handle(self, *args, **options):
		help='data patch for missing sources & missing middle passage length variable on 429 voyages, july 2026'
		zotero_group_id=5290782
		#imno zotero group
		library_type=zotero_credentials['library_type']
		api_key=zotero_credentials['api_key']
		
		data_base_dir='document/management/commands/data'
		
		json_files=[f for f in os.listdir(data_base_dir) if
			not f.startswith('.') and
			f.endswith('.json')
		]
		
		
		zot = Zotero(zotero_group_id, library_type, api_key)
		template= zot.item_template(itemtype='manuscript')
		print(template)

		for j in json_files:
			d=open(os.path.join(data_base_dir,j),'r')
			t=d.read()
			d.close()
			j=json.loads(t)
			if j:
				voyage_id=j['var_voyage_id']
				print(voyage_id)
				voyage=Voyage.objects.get(voyage_id=voyage_id)
				length_middle_passage_days=j['var_length_middle_passage_days']
				sources=j['var_sources']
				for source in sources:
					split_source=source.split(', ')
					shortref=split_source[0]
					rest_of_ref=', '.join(split_source[1:])
					template['title']=rest_of_ref
					template['shortTitle']=shortref
					test=zot.create_items([template])
					zotero_item_id=test['success']['0']
# 					print(zotero_item_id)
					shortref,isnew=ShortRef.objects.get_or_create(name=shortref)
					source=Source.objects.create(
						short_ref=shortref,
						title=rest_of_ref,
						bib=rest_of_ref,
						zotero_group_id=zotero_group_id,
						zotero_item_id=zotero_item_id
					)
					SourceVoyageConnection.objects.create(
						source=source,
						voyage=voyage
					)
					
					
					length_middle_passage_days=j['var_length_middle_passage_days']
					if length_middle_passage_days is not None:
						print("--->",length_middle_passage_days)
						voyagedates=VoyageDates.objects.get(voyage__voyage_id=voyage_id)
						print("--->",voyagedates)
						voyagedates.length_middle_passage_days=length_middle_passage_days
						voyagedates.save()
						print(voyagedates.length_middle_passage_days)
						voyagedates=VoyageDates.objects.get(voyage__voyage_id=voyage_id)
						print(voyagedates.length_middle_passage_days)
						print("-------")
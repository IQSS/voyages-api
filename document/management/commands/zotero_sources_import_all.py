from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from document.models import Source, Transcription, SourceType,DocSparseDate,ShortRef
from xml.etree import ElementTree
import json
import re
import requests
#adding in authorization and urls from localsettings
from voyages3.localsettings import VOYAGES_FRONTEND_BASE_URL,zotero_credentials
from voyages3.settings import STATIC_ROOT
from pyzotero import zotero


_dublin_core_labels = {
	"abstract": "Abstract",
	"accessRights": "Access Rights",
	"accrualMethod": "Accrual Method",
	"accrualPeriodicity": "Accrual Periodicity",
	"accrualPolicy": "Accrual Policy",
	"alternative": "Alternative Title",
	"audience": "Audience",
	"available": "Date Available",
	"bibliographicCitation": "Bibliographic Citation",
	"conformsTo": "Conforms To",
	"contributor": "Contributor",
	"coverage": "Coverage",
	"created": "Date Created",
	"creator": "Creator",
	"date": "Date",
	"dateAccepted": "Date Accepted",
	"dateCopyrighted": "Date Copyrighted",
	"dateSubmitted": "Date Submitted",
	"educationLevel": "Audience Education Level",
	"extent": "Extent",
	"format": "Format",
	"hasFormat": "Has Format",
	"hasPart": "Has Part",
	"hasVersion": "Has Version",
	"identifier": "Identifier",
	"instructionalMethod": "Instructional Method",
	"isFormatOf": "Is Format Of",
	"isPartOf": "Is Part Of",
	"isReferencedBy": "Is Referenced By",
	"isReplacedBy": "Is Replaced By",
	"isRequiredBy": "Is Required By",
	"issued": "Date Issued",
	"isVersionOf": "Is Version Of",
	"language": "Language",
	"license": "License",
	"mediator": "Mediator",
	"medium": "Medium",
	"modified": "Date Modified",
	"provenance": "Provenance",
	"publisher": "Publisher",
	"references": "References",
	"relation": "Relation",
	"replaces": "Replaces",
	"requires": "Requires",
	"rights": "Rights",
	"rightsHolder": "Rights Holder",
	"source": "Source",
	"spatial": "Spatial Coverage",
	"subject": "Subject",
	"tableOfContents": "Table Of Contents",
	"temporal": "Temporal Coverage",
	"valid": "Date Valid",
	"description": "Description",
	"title": "Title",
	"type": "Type",
	"DCMIType": "DCMI Type Vocabulary",
	"DDC": "DDC",
	"IMT": "IMT",
	"LCC": "LCC",
	"LCSH": "LCSH",
	"MESH": "MeSH",
	"NLM": "NLM",
	"TGN": "TGN",
	"UDC": "UDC",
	"Box": "DCMI Box",
	"ISO3166": "ISO 3166",
	"ISO639-2": "ISO 639-2",
	"ISO639-3": "ISO 639-3",
	"Period": "DCMI Period",
	"Point": "DCMI Point",
	"RFC1766": "RFC 1766",
	"RFC3066": "RFC 3066",
	"RFC4646": "RFC 4646",
	"RFC5646": "RFC 5646",
	"URI": "URI",
	"W3CDTF": "W3C-DTF",
	"Agent": "Agent",
	"AgentClass": "Agent Class",
	"BibliographicResource": "Bibliographic Resource",
	"FileFormat": "File Format",
	"Frequency": "Frequency",
	"Jurisdiction": "Jurisdiction",
	"LicenseDocument": "License Document",
	"LinguisticSystem": "Linguistic System",
	"Location": "Location",
	"LocationPeriodOrJurisdiction": "Location, Period, or Jurisdiction",
	"MediaType": "Media Type",
	"MediaTypeOrExtent": "Media Type or Extent",
	"MethodOfAccrual": "Method of Accrual",
	"MethodOfInstruction": "Method of Instruction",
	"PeriodOfTime": "Period of Time",
	"PhysicalMedium": "Physical Medium",
	"PhysicalResource": "Physical Resource",
	"Policy": "Policy",
	"ProvenanceStatement": "Provenance Statement",
	"RightsStatement": "Rights Statement",
	"SizeOrDuration": "Size or Duration",
	"Standard": "Standard",
	"Collection": "Collection",
	"Dataset": "Dataset",
	"Event": "Event",
	"Image": "Image",
	"InteractiveResource": "Interactive Resource",
	"MovingImage": "Moving Image",
	"PhysicalObject": "Physical Object",
	"Service": "Service",
	"Software": "Software",
	"Sound": "Sound",
	"StillImage": "Still Image",
	"Text": "Text",
	"domainIncludes": "Domain Includes",
	"memberOf": "Member Of",
	"rangeIncludes": "Range Includes",
	"VocabularyEncodingScheme": "Vocabulary Encoding Scheme"
}

_max_errors = 5 # Maximum number of *consecutive* errors for the APIs we call.
# _voyages_cache_filename = '.cached_voyages_data'
_zotero_cache_filename = f'{STATIC_ROOT}/.cached_zotero_data'

def _makeLabelValue(label, value, lang):
	return { 'label': { lang: [label] }, 'value': { lang: value } }

class Command(BaseCommand):
	help = """This command fetches data from the Zotero API and imports it to the Voyages Document models"""
	
	def add_arguments(self, parser):
		# We shouldn't need these any more
# 		parser.add_argument("--voyages-key")
# 		parser.add_argument("--voyages-url")
		# But we will need this
		parser.add_argument("--voyages-frontend", default=VOYAGES_FRONTEND_BASE_URL)
		parser.add_argument("--zotero-key", default=zotero_credentials['api_key'])
		parser.add_argument("--zotero-url", default="https://api.zotero.org")
		parser.add_argument("--zotero-userid", default=zotero_credentials['userid'])
		parser.add_argument("--ignore-cache", default=True)

	@staticmethod
	def _get_zotero_data(options, group_ids: list[int]):
		# Check if we already have cached data from the Zotero API.
		#May 29 -- this isn't working for some reason?
# 		if not options.get('--ignore-cache', False):
# 			try:
# 				with open(_zotero_cache_filename, encoding='utf-8') as f:
# 					cached = json.load(f)
# 					print(f"Importing Zotero entries from cached file. {len(cached.keys())} group libraries are present...")
# 					for group_id in cached:
# 						print(f"+Library ID {group_id} has {len(cached[group_id].keys())} items.")
# 					
# 					return cached
# 			except:
# 				print("No cached Zotero data")

		def extract_from_rdf(rdf):
			# Map all the entries first and later keep only those that have a
			# Dublin Core label, and for those we use that label for the key
			# value instead of the original XML tag's name.
			complete = {}
			for e in rdf:
				key = re.match('^{.*}(.*)$', e.tag)[1]
				val = complete.setdefault(key, [])
				val.append(e.text)
			return { _dublin_core_labels[key]: val
					for key, val in complete.items() if key in _dublin_core_labels }

		def zotero_page(start: int, group_id: str, limit=100):
			res = requests.get( \
				f"{options['zotero_url']}/groups/{group_id}/items?" + \
				f"start={start}&limit={limit}&content=rdf_dc", \
				headers={ 'Authorization': f"Bearer {options['zotero_key']}" }, \
				timeout=60)
			page = ElementTree.fromstring(res.content)
			# Select the content nodes and navigate through RDF elements until
			# we reach http://www.w3.org/1999/02/22-rdf-syntax-ns#Description.
			# The following will build a dictionary, indexed by Zotero ids,
			# where each entry is the RDF data of the Zotero item.
			entries = {
				e.find('{http://zotero.org/ns/api}key').text:
					e.find('.//{http://www.w3.org/2005/Atom}content/*[1]/*[1]') for
					e in page.findall('.//{http://www.w3.org/2005/Atom}entry')
			}
			count = len(entries)
			
			# Replace the XML element in the dict values by a dictionary of RDF
			# attributes with their respective values.
			page = {
				key: extract_from_rdf(rdf)
				for key, rdf in entries.items() if rdf is not None
			}
			
			return (page, count)

		zotero_data = {}
		for group_id in group_ids:
			#I think we need a nested dictionary
			## in case item id's turn out not to be unique between group libraries...
			zotero_data[group_id]={}
			zotero_start = 0
			error_count = 0
			last_error = None
			while True:
				if error_count >= _max_errors:
					raise Exception(f"Too many failures fetching data from the Zotero API: {last_error}")
				try:
					(page, count) = zotero_page(zotero_start, group_id, 100)
					print(f"Fetched {count} records from Zotero's API/{len(page)} items with proper data.")
					if count == 0:
						break
					zotero_start += count
					zotero_data[group_id].update(page)
					error_count = 0
				except Exception as ex:
					last_error = ex
					error_count += 1
			# Now get bib info from Zotero.
			error_count = 0
			zotero_start = 0
			while True:
				if error_count >= _max_errors:
					raise Exception(f"Too many failures fetching data from the Zotero API: {last_error}")
				try:
					res = requests.get( \
						f"{options['zotero_url']}/groups/{group_id}/items?start={zotero_start}" + \
						"&limit=100&format=json&include=bib&style=chicago-fullnote-bibliography", \
						headers={ 'Authorization': f"Bearer {options['zotero_key']}" }, \
						timeout=60)
					page = res.json()
					if not page:
						break
					print(f"Fetched bibliography from Zotero's API [{len(page)}].")
					for item in page:
						key = item['key']
						if key in zotero_data[group_id]:
							zd = zotero_data[group_id][key]
							zd['bib'] = item['bib']
							zd['zotero_doc_url'] = item['links']['alternate']['href']
					zotero_start += len(page)
				except Exception as ex:
					last_error = ex
					error_count += 1
		# Save to a local cache
		try:
			with open(_zotero_cache_filename, 'w', encoding='utf-8') as f:
				json.dump(zotero_data, f)
		except:
			print("Failed to write Zotero data to the cache")
		return zotero_data
	
	
# 	@staticmethod
# 	def _map_connections(doc, etype, connections, field_name):
# 		conn = set()
# 		for item in connections:
# 			if item.get(field_name):
# 				entity_key = item[field_name].get('id')
# 				if entity_key:
# 					conn.add(entity_key)
# 		for ekey in conn:
# 			edoc = EntityDocument(document=doc, entity_type=etype, entity_key=ekey)
# 			edoc.save()

	@staticmethod
	def _extract_iiif_url(url):
		if url is None or url == '':
			return None
		m = re.match('^(https?://)([^/]+)(.*)/full/(full|max)/0/default.jpg$', url)
		if not m:
			raise Exception(f"Bad format for IIIF url: '{url}'")
		return [m.group(i) for i in [2, 3]]
	
	def handle(self, *args, **options):
		# Log into Zotero with specified username
		zotero_groups_url = f"{options['zotero_url']}/users/{options['zotero_userid']}/groups"
		zotero_headers = { 'Authorization': f"Bearer {options['zotero_key']}" }
		res = requests.get(
			zotero_groups_url,
			timeout=30,
			headers=zotero_headers
		)
		
		#we need to use pyzotero if we're creating items from scratch based on shortrefs
		#this needs a refurbish
		
		# Retrieve the group ids from the Zotero API.
		# Specifically, those that the logged-in user has access to
		##
# 		group_ids = [item['id'] for item in res.json() if item['data']['name']]
		
		#INSTEAD, WE'RE GOING TO MANUALLY SET ZOTERO GROUP LIBRARIES AS PULLABLE
		#BECAUSE WE'RE TREATING IT AS OUR SOURCE OF TRUTH ON THE BIBLIOGRAPHIC DATASET
		group_ids=zotero_credentials['import_from_library_ids']
		print(f"Zotero group ids are: {group_ids}")
		zotero_data = Command._get_zotero_data(options, group_ids)
				
		timestamp_format = "%Y-%m-%dT%H:%M:%S.%fZ"
		imported_count = 0
		
		#So I've turned this around -- now we treat Zotero as our bibliographic source of truth
		##Rather than pulling source data then looking for the corresponding zotero entry
		##We pull zotero data and look for the corresponding source entry
		###Down the line, we'll need a way to identify if a source has been
		####Added to SV without being added to Zotero?
		####Or god forbid somehow deleted from Zotero
		##But my thinking here is that the contribute form should have a zotero widget
		##So that people can create sources to go with their contributions
		library_id=zotero_credentials['import_from_library_ids']
		library_type=zotero_credentials['library_type']
		api_key=zotero_credentials['api_key']
		
		
		imported_count=0
		with transaction.atomic():
			for zotero_group_id in zotero_data:
				print(zotero_group_id)
				zot = zotero.Zotero(zotero_group_id, library_type, api_key)
				for zotero_item_id in zotero_data[zotero_group_id]:
					print(zotero_item_id)
				
					#get the core archival metadata (jcm)
					rdf = zotero_data[zotero_group_id][zotero_item_id]		
							
					zotero_url = rdf.pop('zotero_doc_url',None)
					bib = rdf.pop('bib', None)
					source_title = rdf.pop('Title','No title')
					source_type_name = rdf.pop('Type',None)
					source_date = rdf.pop("Date",None)
				
					## We really should be enforcing a standard date format but... (jcm)
					if source_date is not None:
						source_date=source_date[0]
						slashes=re.fullmatch("[0-9]*/[0-9]*/[0-9]*",source_date)
						dashes=re.fullmatch("[0-9]*-[0-9]*-[0-9]*",source_date)
						at_least_a_year=re.search('[0-9]{4}',source_date)
						if slashes:
							yyyy,mm,dd=[int(i) if i!='' else None for i in source_date.split("/")]
						elif dashes:
							yyyy,mm,dd=[int(i) if i!='' else None for i in source_date.split("-")]
						elif at_least_a_year:
							yyyy=int(at_least_a_year.group(0))
							mm=dd=None
							print("BAD DATE FORMAT, RECORDING YEAR:",yyyy,zotero_url)
						elif source_date=="No Date":
							yyyy=mm=dd=None
						else:
							yyyy=mm=dd=None
							print("UNABLE TO PARSE DATE:",zotero_url,source_date)
				
					# Check to see if the source is in the database (jcm)
					try:
						source=Source.objects.get(zotero_item_id=zotero_item_id)
					except:
						print("SOURCE DOES NOT EXIST IN VOYAGES:",zotero_url)
						source=None
				
					#proceed if we have a match in the database for that source (jcm)
					if source is not None:
						#AS FAR AS I CAN TELL, TYPE IS EITHER NONE OR 1 ENTRY LONG
						#But for some reason Zotero encodes them as arrays? (jcm)
						if source_type_name is not None:
							source_type_name=source_type_name[0]
							#zotero's types are all lowercase. we're going to capitalize them
							#and use them as a controlled vocabulary
							source_type,source_type_isnew=SourceType.objects.get_or_create(
								name=source_type_name.capitalize()
							)
							source.source_type=source_type
						else:
							source.source_type=None
				
						if source.zotero_group_id is None:
							source.zotero_group_id=zotero_group_id
					
						#SIMILARLY, TITLE IS EITHER NONE OR A 1-ENTRY ARRAY
						if source_title is not None:
							source_title=source_title[0]
						
						source.title=source_title
				
						source.zotero_url = zotero_url
				
						source.bib=bib
					
						#get any existing attached date object
						#and overwrite it or delete it as necessary
						#or create a new one if it does not (as necessary)
						if not (yyyy is None and mm is None and dd is None):
							if source.date is not None:
								source_date_obj=source.date
							else:
								source_date_obj=DocSparseDate.objects.create(
									year=yyyy,
									month=mm,
									day=dd
								)
							source.date=source_date_obj
						else:
							if source.date is not None:
								source_date_obj=source.date
								source_date_obj.delete()
							source.sparse_date=None
					
						#if there are pages (which in my schema always have images) ...
						#then we'll pull in the dcterms data for use by the manifest generator
						#but all the other data (citation, transcriptions, etc) are all included
						#in the schema already
						if source.page_connections.all().count() > 0:
							metadata = [_makeLabelValue(k, val, 'en') for k, val in rdf.items()]
# 							print(metadata)
							source.manifest_content = {
								'metadata': metadata
							}
						else:
							source.manifest_content=None
					
						source.save()
					else:
						#I think we should actually go ahead and create the source if it doesn't exist
						#But until we make that call, I'm leaving this alone! (jcm)
						zot = zotero.Zotero(zotero_group_id, library_type, api_key)
						i=zot.item(zotero_item_id)
						short_ref=i['data']['shortTitle']
						
						short_ref_obj,short_ref_obj_isnew=ShortRef.objects.get_or_create(
							name=short_ref
						)
						
						if source_type_name is not None:
							source_type_name=source_type_name[0]
							#zotero's types are all lowercase. we're going to capitalize them
							#and use them as a controlled vocabulary
							source_type,source_type_isnew=SourceType.objects.get_or_create(
								name=source_type_name.capitalize()
							)
						else:
							source_type=None
					
						#SIMILARLY, TITLE IS EITHER NONE OR A 1-ENTRY ARRAY
						if source_title is not None:
							source_title=source_title[0]
					
						#get any existing attached date object
						#and overwrite it or delete it as necessary
						#or create a new one if it does not (as necessary)
						if not (yyyy is None and mm is None and dd is None):
							source_date_obj=DocSparseDate.objects.create(
								year=yyyy,
								month=mm,
								day=dd
							)
						
						source=Source.objects.create(
							title=source_title,
							date=source_date_obj,
							source_type=source_type,
							zotero_url=zotero_url,
							zotero_group_id=zotero_group_id,
							zotero_item_id=zotero_item_id,
							zotero_grouplibrary_name="",
							short_ref=short_ref_obj
						)
						source.save()

					
					imported_count += 1
					if imported_count % 100 == 0:
						print(f"Imported {imported_count} documents")
		print("Import finished")

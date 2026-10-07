"""
Management command for generating IIIF manifests
"""

import json
import pathlib
import re
import time
import requests
from django.db.models import Q
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Prefetch
from document.models import Source
from common.s3_utils import *
from voyages3.localsettings import VOYAGES_FRONTEND_BASE_URL
import os

# We special case these sources as they have issues with their IIIF Image
# Service preventing us from creating manifests that point directly to the image
# service, instead manifests from these sources will link directly to the image
# files.
_special_case_no_img_service = ['catalog.archives.gov']

def get_api_and_profile(img_info):

	profile_source = img_info['profile']
	if type(profile_source)==list:
		#Michigan did something screwy...
		profile_source=profile_source[0]
	print(profile_source,type(profile_source))
	level_match = re.match('.*(level[0-9]).*', profile_source)
	context = img_info.get('@context', '')
	print(context)
	api_match = re.match(".*/api/image/([0-9]+).*", context)
	print(api_match)
	api_version = api_match.group(1) if api_match else None
	return (api_version, level_match.group(1) if level_match else None)

class Command(BaseCommand):
	"""
	IIIF manifest generation command
	"""

	help = """This command generate manifest files based on the documents
		in the database that have page images attached to them."""

	def add_arguments(self, parser):
		parser.add_argument("--iiif-manifests-baseurl",default=iiif_manifests_baseurl)
		parser.add_argument("--skip-existing",default=True,
							help="We are having timeout issues fetching remote manifests for repurposing. This serves as a basic checkpoint.")
		parser.add_argument("--shortref", default=None,help="target only sources matching (icontains) this string.")

	@staticmethod
	def _extract_iiif_url(url):
		if url is None or url == '':
			return None
		m = re.match('^(https?://)([^/]+)(.*)/full/(full|max)/0/default.jpg$', url)
		if not m:
			raise Exception(f"Bad format for IIIF url: '{url}'")
		return [m.group(i) for i in [2, 3]]

	def handle(self, *args, **options):
		
		#NOT RUNNING THIS EXCEPT LOCALLY W/O DJK's APPROVAL
# 		exit()
		#screen out sources that lack either pages  
		sources = Source.objects \
			.prefetch_related('page_connections') \
			.prefetch_related('page_connections__page') \
			.prefetch_related('page_connections__page__transcriptions') \
			.prefetch_related('source_voyage_connections__voyage') \
			.prefetch_related('source_enslaver_connections__enslaver') \
			.prefetch_related('source_enslaved_connections__enslaved') \
			.filter(
				~Q(page_connections__page=None)
			)
		
		shortref=options['shortref']
		if shortref is not None:
			sources=sources.filter(short_ref__name__icontains=shortref)
		
		print(f"Found {sources.count()} sources with page images.")
		
		if options['skip_existing'] in [True,'true','True']:
			precount=sources.count()
			sources=sources.filter(has_published_manifest=False)
			if sources.count()<precount:
				print(f"however, you have elected to skip those that already have manifests. we will only be publishing new manifests for the {sources.count()} items that lack them.")
			else:
				print("We will publish manifests for all of them.")
		else:
			print("We will clear all manifests and re-publish all of them.")
			
			cleared_sources=list(sources)
			for s in cleared_sources:
				s.has_published_manifest = False
			
			Source.objects.bulk_update(cleared_sources, ["has_published_manifest"])
			
		generated_count=0
		
		for source in sources:
			with transaction.atomic():
				print("--->",source.title)
				content = source.manifest_content
# 				print("------->",content)
				
				#then do a final pass to ensure that we don't have "pages" without images
				#some of those did sneak in during the process of indexing transkribus against the library collections
				pages_with_images = [spc.page for spc in source.page_connections.all() if spc.page.iiif_baseimage_url not in [None,'']]
				
				if len(pages_with_images)==0:
					# Do not generate manifest without images.
					print(f"source {source.id} {source} has no images?")
					continue
				
				# Generate manifest for this revision.
				## THIS SHOULD BE UPDATED TO A COMPOSITE KEY: zotero_group_id + zotero_item_id
				base_id = f"{iiif_manifests_baseurl}{source.zotero_group_id}__{source.zotero_item_id}.json"
				first_thumb = None
				canvas = []
				abort = False
				for i, page in enumerate(pages_with_images, 1):
					print(page.__dict__)
					iiif_baseimage_url=page.iiif_baseimage_url
					# A canvas page.
					host_addr,iiif_suffix = Command._extract_iiif_url(iiif_baseimage_url)
					img_url_base = f"https://{host_addr}{iiif_suffix}"
					
					error_count=0

					max_errors=1
					standoff=2
					while True:
						try:
							req=requests.get(f"{img_url_base}/info.json", timeout=30)
							print(req)
							req_succeeded=True
						except:
							print("Request timeout. Pausing...")
							req_succeeded=False
						
						
						
						if req.status_code!=200 or not req_succeeded:
							if req_succeeded:
								print(req.status_code)
							print("error fetching",img_url_base)
							error_count+=1
							if error_count>max_errors:
								break
							standoff=standoff**2
							time.sleep(standoff)
						else:
							img_info=req.json()
							break
					
					(api_version, profile_level) = get_api_and_profile(img_info)
					
					use_img_service = not any(s in host_addr for s in _special_case_no_img_service)
					if use_img_service and not (api_version and profile_level):
						print("Failed to find API version and level for image service: " +
							  f"{rev.label} [{rev.document.key}]")
						abort = True
						break
					thumb = [
						{
							"id": f"{img_url_base}/full/300,300/0/default.jpg",
							"type": "Image",
							"format": "image/jpeg"
						}
					]
					if i == 1:
						first_thumb = thumb
					w = int(img_info['width'])
					h = int(img_info['height'])
					max_dim = max(w, h)
					max_len = 1920
					if max_dim > max_len:
						w = int(round(w * max_len / max_dim))
						h = int(round(h * max_len / max_dim))
					img_size_urlparam = f"{w},{h}" if use_img_service else 'max'
					canvas_body = {
						"id": f"{img_url_base}/full/{img_size_urlparam}/0/default.jpg",
						"type": "Image",
						"format": "image/jpeg",
						"width": img_info['width'],
						"height": img_info['height']
					}
					if use_img_service:
						canvas_body['service'] = [{
							"id": img_url_base,
							"type": f"ImageService{api_version}",
							"profile": profile_level
						}]
					canvas_id = f"{base_id}/canvas{i}"
					canvas_data = {
						"id": canvas_id,
						"type": "Canvas",
						"thumbnail": thumb,
						"height": h,
						"width": w,
						"items": [{
							"id": f"{canvas_id}/item1",
							"type": "AnnotationPage",
							"items": [{
								"id": f"{canvas_id}/item1/image1",
								"type": "Annotation",
								"motivation": "painting",
								"body": canvas_body,
								"target": canvas_id
							}]
						}]
					}
					transcriptions = page.transcriptions.all()
					if len(transcriptions)>0:
						canvas_data["annotations"] = [{
							"id": f"{canvas_id}/annopage{i}",
							"type": "AnnotationPage",
							"items": [{
								"id": f"{canvas_id}/annopage{i}/anno1",
								"type": "Annotation",
								"motivation": "commenting",
								"body": {
									"type": "TextualBody",
									"language": t.language_code,
									"format": "text/html",
									"value": t.text
								},
								"target": canvas_id
							}]
						} for t in transcriptions]
					canvas.append(canvas_data)
				if abort:
					break
				# Append entity connections to metadata.
				doc_links = {}
				
				if content is not None:
					metadata = list(content['metadata'])
				else:
					metadata=[]
				
				#voyage ids
				source_voyages=source.source_voyage_connections.all()
				if source_voyages.count()>0:
					voyage_links={
						"label": { 'en': ["Linked Voyages"] },
						"value": { 'en': [] }
					}
					for source_voyage in source_voyages:
						voyage_id=source_voyage.voyage.voyage_id
						link=f"<span><a href='{VOYAGES_FRONTEND_BASE_URL}voyage/{voyage_id}'>Voyage #{voyage_id}</a></span>"
						voyage_links['value']['en'].append(link)
					metadata.append(voyage_links)
					
				source_enslavers=source.source_enslaver_connections.all()
				if source_enslavers.count()>0:
					enslaver_links={
						"label": { 'en': ["Linked Enslavers"] },
						"value": { 'en': [] }
					}
					for source_enslaver in source_enslavers:
						enslaver_id=source_enslaver.enslaver.id
						enslaver_principal_alias=source_enslaver.enslaver.principal_alias
						link=f"<span><a href='{VOYAGES_FRONTEND_BASE_URL}enslaver/{enslaver_id}'>{enslaver_principal_alias} #{enslaver_id}</a></span>"
						enslaver_links['value']['en'].append(link)
					metadata.append(enslaver_links)
				
				source_enslaved_people=source.source_enslaved_connections.all()
				if source_enslaved_people.count()>0:
					enslaved_links={
						"label": { 'en': ["Linked Enslaved People"] },
						"value": { 'en': [] }
					}
					for source_enslaved_person in source_enslaved_people:
						enslaved_id=source_enslaved_person.enslaved.enslaved_id
						enslaved_documented_name=source_enslaved_person.enslaved.documented_name
						link=f"<span><a href='{VOYAGES_FRONTEND_BASE_URL}enslaved/{enslaved_id}'>{enslaved_documented_name} #{enslaved_id}</a></span>"
						enslaved_links['value']['en'].append(link)
					metadata.append(enslaved_links)
				
				if type(source.title)!=list:
					published_title=[source.title]
				else:
					published_title=source.title
				
				manifest = {
					"@context": "http://iiif.io/api/presentation/3/context.json",
					"id": base_id,
					"type": "Manifest",
					"label": { 'en': published_title },
					"metadata": metadata,
					"viewingDirection": "left-to-right",
					"behavior": ["paged"],
					"thumbnail": first_thumb,
					"items": canvas
				}
				
				
				filename = f"{source.zotero_group_id}__{source.zotero_item_id}.json"
				
				push_item_to_s3(filename,bytes(json.dumps(manifest).encode('UTF-8')))
				source.thumbnail = first_thumb[0]['id']
				source.has_published_manifest=True
				source.save()
				generated_count += 1
				if generated_count % 50 == 0:
					print(f"Generated {generated_count} manifests")
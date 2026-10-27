from django.core.management.base import BaseCommand, CommandError
import json
import urllib3
import urllib
import xml.etree.ElementTree as ET
from document.models import *
from past.models import *
from voyage.models import *
from voyages3.localsettings import transkribus_credentials,transkribus_collection_ids
import requests
import re
import os

def authenticate():
	
	auth_url="https://transkribus.eu/TrpServer/rest/auth/login"
	
	payload=urllib.parse.urlencode(transkribus_credentials)
	
	headers={'Content-Type': 'application/x-www-form-urlencoded'}
	
	response = requests.request("POST", auth_url, headers=headers, data=payload)
	
	if response.status_code!=200:
		print("error",response,response.text)
		exit()

	root = ET.fromstring(response.text)
	sessionId=[c.text for c in root if c.tag=='sessionId'][0]
	headers['Cookie']='='.join([ 'JSESSIONID',sessionId])
	return headers


class Command(BaseCommand):
	help = 'hits transkribus, pulls down image transcriptions'
	def handle(self, *args, **options):
		
		#when the non-BL images were re-uploaded using their smaller jpg files to be processable
		#we lost the filenames. so now we're just going to have to count on pagination doing the trick for us
		
		#1. authenticate
		auth_headers=authenticate()
		
		print("auth headers:",auth_headers)
		
		collections_url='https://transkribus.eu/TrpServer/rest/collections/list'
		
		resp=requests.get(collections_url,headers=auth_headers)
		
		j=json.loads(resp.text)
		
		transkribus_shortrefs=ShortRef.objects.all().exclude(transkribus_docId=None)
		
		print(transkribus_shortrefs)
		
		transkribus_collection_id=transkribus_collection_ids[0]
		
		
		
		page_pks=transkribus_shortrefs.values_list('transkribus_docId','short_ref_sources__page_connections__page__id')
		print(page_pks)
		pd={}
		for ppk in page_pks:
			a,b=ppk
			if b is not None:
				if a in pd:
					pd[a].append(b)
				else:
					pd[a]=[b]
		
		for docId in pd:
# 			if docId not in ['25566', '25565', '25564', '25563', '25562', '25561', '25560', '25555', '25552', '25554', '25553', '25551', '25550', '25575', '25557', '25567', '25556', '25510', '25509', '25508', '25506', '25507', '25505', '25504', '25503', '25502', '25501', '25500', '25582', '25576', '25577','1437762','1470747','1470827','1470863','1470876','1487718','1487721','1492986','1493090','1493096','1494915','1494931','1496973','1497235']:
			if docId not in ['1437762', '1439396', '1438141']:
				break
			print('DOCID',docId)
			pages=pd[docId]
			pages.sort()
			print('PAGES',pages)
			
			for pagepk in pages:
				page=Page.objects.get(id=pagepk)
				print(page)
				page.transkribus_pageid=None
				page.save()
			
			doc_url="https://transkribus.eu/TrpServer/rest/collections/%s/%s/fulldoc" %(transkribus_collection_id,docId)
			resp=requests.get(doc_url,headers=auth_headers)
			doc=json.loads(resp.text)
			
			c=1
			for transkribus_page in doc['pageList']['pages']:
				pagetexturls=[]
				
				imgFileName=transkribus_page['imgFileName']
				
				imgFileName_stripped=re.sub('(\.jpg|\.tif|\.tiff)','',imgFileName)
				
				skip=False
				try:
					sp=Page.objects.get(image_filename__icontains=imgFileName_stripped)
					print(sp.source_connections.first().source)
				except:
					print(f"IMAGE MATCHING FILENAME DOES NOT EXIST:{imgFileName_stripped}")
					skip=True
				if not skip:
					if sp.transcriptions.all().count() != 0:
						print(sp.transcriptions.all())
						print("transcription already exists")
					else:
						imgFileName=transkribus_page['imgFileName']
						
						## but as a backstop we can capture the pageid on the transkribus side as well
						## and then bump them as necessary and re-pull (i don't want to do this!!!!)
						transkribus_pageId=transkribus_page['pageId']
						transcripts=transkribus_page['tsList']['transcripts']
						pagetext=''
						max_ts=0
						transcript=transcripts[0]
						
						if transcript is not None:
						
							wordcount=transcript['nrOfCharsInLines']
							if wordcount>0:
								transcript_url=transcript['url']
								connection_pool = urllib3.PoolManager()
								resp = connection_pool.request('GET',transcript_url,headers=auth_headers)
								tmpfilename="document/management/commands/data/%s.xml" %docId
								f = open(tmpfilename, 'wb')
								f.write(resp.data)
								f.close()
								resp.release_conn()
								d=open(tmpfilename,"r")
								t=d.read()
								d.close()
								pagetree=ET.fromstring(t)
								textlines_trees=[e for e in pagetree.iter() if e.tag=="{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}TextLine"]
								textlines=[]
								
								os.remove(tmpfilename)
								
								for textline_tree in textlines_trees:
									linetext=[e.text for e in textline_tree.iter() if e.tag=='{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}Unicode' and e.text is not None]
									textlines.append(' '.join(linetext))
								pagetext+='\n'.join(textlines)
						print(pagetext)
						if re.match('\s+',pagetext,re.S):
							pagetext=""
						
						Transcription.objects.create(
							page=sp,
							language_code='en',
							text=pagetext,
							is_translation=False
						)
					

				c+=1
# 				if c>10:
# 					exit()
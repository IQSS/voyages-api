import csv
import re
from pyzotero import zotero
from django.core.management.base import BaseCommand, CommandError
from document.models import *
from past.models import *
from voyage.models import *
import requests
import multiprocessing
import json
import os
from django import db


def index_voyages(enslaver_voyage_values_list):
	voyages_dict={
		o.id:o for o in Voyage.objects.all()
	}
	c=0
	print('voyages',len(enslaver_voyage_values_list))
	for evv in enslaver_voyage_values_list:
		id,v_id=evv
		if v_id is not None:
			enslaver_identity=EnslaverIdentity.objects.get(id=id)
			voyage=Voyage.objects.get(id=v_id)
			enslaver_identity.voyages.add(voyage)
		c+=1
		if c%1000==0:
			print(c)


def index_roles(enslaver_roles_values_list):
	c=0
	print('roles',len(enslaver_roles_values_list))
	roles_dict={
		o.id:o for o in EnslaverRole.objects.all()
	}
	for erv in enslaver_roles_values_list:
		id,role_id=erv
		if role_id is not None:
			enslaver_identity=EnslaverIdentity.objects.get(id=id)
			role=roles_dict[role_id]
			enslaver_identity.roles.add(role)
		c+=1
		if c%1000==0:
			print(c)

def purge_m2m_fields(enslaver_ids):
	print("enslaver identities",len(enslaver_ids))
	c=0
	for e_id in enslaver_ids:
		e=EnslaverIdentity.objects.get(id=e_id)
		e.roles.clear()
		e.voyages.clear()
		e.save()
		c+=1
		if c%1000==0:
			print(c)



class Command(BaseCommand):
	help = 'connects enslavers directly to voyages and roles for faster searching'
	def handle(self, *args, **options):
		
		rebuilder_number_of_workers=os.cpu_count()
		
		def get_batches(worklist,rebuilder_number_of_workers):
			batch_size=int(len(worklist)/rebuilder_number_of_workers)
			
			print("BATCH SIZE",batch_size)
			batches=[]
			
			for i in range(rebuilder_number_of_workers):
				
				a=i*batch_size
				b=(i+1)*(batch_size)-1
				
				print("THIS BATCH INDICES",a,b)
				if i!=rebuilder_number_of_workers-1:
					batch=worklist[a:b]
				else:
					batch=worklist[a:]
				batches.append(batch)
			return batches
		
		enslaverIdentities=EnslaverIdentity.objects.all()
		
		## PURGE
		
		processes=[]
		enslaver_ids=[i[0] for i in enslaverIdentities.values_list('id')]
		
		batches=get_batches(enslaver_ids,rebuilder_number_of_workers)
		
		db.connections.close_all()
		
		for batch in batches:
			p = multiprocessing.Process(target=purge_m2m_fields, args=(batch,))
			processes.append(p)
			p.start()
		for p in processes:
			p.join()
		
		
		print("-------")
		
		
		#VOYAGES
		enslaverIdentities=enslaverIdentities.prefetch_related(
			'aliases__enslaver_relations__relation__voyage',
			'aliases__enslaver_relations__roles'
		)
		
		enslaver_voyage_values_list=list(enslaverIdentities.values_list(
			'id',
			'aliases__enslaver_relations__relation__voyage__id'
		))
		
		
		processes=[]
		
		db.connections.close_all()
		
		batches=get_batches(enslaver_voyage_values_list,rebuilder_number_of_workers)
		
		for batch in batches:
			p = multiprocessing.Process(target=index_voyages, args=(batch,))
			processes.append(p)
			p.start()
		
		for p in processes:
			p.join()


		#ROLES
		enslaver_roles_values_list=list(enslaverIdentities.values_list(
			'id',
			'aliases__enslaver_relations__roles__id'
		))

		processes=[]
		
		db.connections.close_all()
		
		batches=get_batches(enslaver_roles_values_list,rebuilder_number_of_workers)
		
		for batch in batches:
			p = multiprocessing.Process(target=index_roles, args=(batch,))
			processes.append(p)
			p.start()
		
		for p in processes:
			p.join()
		
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

def get_batches(worklist,worker_count):
	if worker_count < 1:
		raise ValueError("worker_count must be positive")
	if not worklist:
		return []
	batch_count=min(worker_count,len(worklist))
	base_size,remainder=divmod(len(worklist),batch_count)
	batches=[]
	start=0
	for index in range(batch_count):
		batch_size=base_size+(1 if index < remainder else 0)
		stop=start+batch_size
		batches.append(worklist[start:stop])
		start=stop
	return batches


def purge_m2m_fields(enslaver_ids):
	print("enslaver identities",len(enslaver_ids))
	c=0
	for e_id in enslaver_ids:
		e=EnslaverIdentity.objects.get(id=e_id)
		# Related-manager clear() persists directly. Saving the otherwise
		# unchanged identity would only advance its auto_now last_updated field.
		e.roles.clear()
		e.voyages.clear()
		c+=1
		if c%1000==0:
			print(c)



class Command(BaseCommand):
	help = 'connects enslavers directly to voyages and roles for faster searching'
	def handle(self, *args, **options):
		rebuilder_number_of_workers=max(1,os.cpu_count() or 1)
		
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
		
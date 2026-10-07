import requests
import json
from django.core.management.base import BaseCommand, CommandError
from common.reqs import  getJSONschema
from voyage.models import *
from geo.models import *
from past.models import *
from document.models import *
import pytz
from django.db import IntegrityError

class Command(BaseCommand):
	help = 'takes enslaver relations of type "ownership"  in relation to enslaved people on the same voyage, and turns it into a single relation to those people.'
	def handle(self, *args, **options):
		
		def p2p_rollup(relation_type_name):
			print('ROLLING UP',relation_type_name)
			empty_count=0
			for er in EnslavementRelation.objects.all():
				if er.relation_enslavers.all().count()==0 and \
				er.enslaved_in_relation.all().count()==0:
					empty_count+=1
			print("empty enslavement relations @ start-->",empty_count)
		
			p2p_relations=EnslavementRelation.objects.all().filter(
				relation_type__name=relation_type_name
			)
			
			p2p_enslaved_voyages=p2p_relations.values_list(
				'enslaved_in_relation__enslaved__enslaved_relations__relation__voyage__id',
				'relation_enslavers__enslaver_alias__id',
				'id'
			)
			
			p2p_enslaved_voyage_dict={}
			enslaver_voyage_dict={}
			
			#pull unique triples: voyage ids connected to
			#enslaved people under that form of p2p relation withan enslaver
			for oev in p2p_enslaved_voyages:
				voyage_id,enslaver_alias_id,relation_id=oev
				if voyage_id is not None:
					if voyage_id not in p2p_enslaved_voyage_dict:
						p2p_enslaved_voyage_dict[voyage_id]={
							enslaver_alias_id:[relation_id]
						}
					else:
						if enslaver_alias_id not in p2p_enslaved_voyage_dict[
							voyage_id
						]:
							p2p_enslaved_voyage_dict[voyage_id][enslaver_alias_id]=\
							[relation_id]
						else:
							p2p_enslaved_voyage_dict[voyage_id]\
							[enslaver_alias_id].append(
								relation_id
							)
					if enslaver_alias_id not in enslaver_voyage_dict:
						enslaver_voyage_dict[enslaver_alias_id]=[voyage_id]
					else:
						enslaver_voyage_dict[enslaver_alias_id].append(voyage_id)
			
			#establish a canonical relation
			for v_id in p2p_enslaved_voyage_dict:
				print("voyage:",v_id)
				enslaver_alias_ids=p2p_enslaved_voyage_dict[v_id]
				voyage=Voyage.objects.get(id=v_id)
				for enslaver_alias_id in enslaver_alias_ids:
					voyage_enslaver_ownership_relation_ids=\
					list(set(p2p_enslaved_voyage_dict[v_id][enslaver_alias_id]))
					canonical_relation_id=min(voyage_enslaver_ownership_relation_ids)
					relation=EnslavementRelation.objects.get(id=canonical_relation_id)
					relation.voyage=voyage
					relation.save()
					#reroute all
					#enslaved_in_relation and
					#enslaver_in_relations
					#to the canonical relation
					if len(voyage_enslaver_ownership_relation_ids)>1:
						other_relation_ids=voyage_enslaver_ownership_relation_ids[1:]
						relation.voyage=voyage
						for or_id in other_relation_ids:
							other_relation=EnslavementRelation.objects.get(id=or_id)
							other_enslavedirs=other_relation.enslaved_in_relation.all()
							for oeir in other_enslavedirs:
								oeir.relation=relation
								oeir.save()
							other_enslaverirs=other_relation.relation_enslavers.all()
							for oeir in other_enslaverirs:
								if oeir.enslaver_alias.id==enslaver_alias_id:
									oeir.delete()
							other_relation=EnslavementRelation.objects.get(id=or_id)
# 							print(other_relation,other_relation.relation_enslavers.all(),other_relation.enslaved_in_relation.all())
						for or_id in other_relation_ids:
							other_relation=EnslavementRelation.objects.get(id=or_id)
						relation.save()
			
			empty_count=0
			for er in EnslavementRelation.objects.all():
				if er.relation_enslavers.all().count()==0 and \
				er.enslaved_in_relation.all().count()==0:
					empty_count+=1
					er.delete()
			print("empty relations after rollup (now deleted)-->",empty_count)
		
		#roll up enslavers and enslaved who have the same type of relation spread 
		#across several relation objects into one relation object
		for relation_type_name in ['Transportation','Ownership','Transaction']:
			p2p_rollup(relation_type_name)
		
		voyages=Voyage.objects.all()
		#roll up enslavers who have a no-enslaved-people-transportation
		#into a single transportation relation
		c=0
		for voyage in voyages:
			print(voyage)
			voyage_enslavement_relations=voyage.voyage_enslavement_relations.all().filter(
				relation_type__name="Transportation",
				enslaved_in_relation=None
			)
			investor_role=EnslaverRole.objects.get(name="Investor")
			for ver in voyage_enslavement_relations:
				enslaver_relations=ver.relation_enslavers.all()
				for er in enslaver_relations:
					for role in er.roles.all():
						if role.name=="Owner":
							er.roles.remove(role)
							er.roles.add(investor_role)
							er.save()
							
			if voyage_enslavement_relations.count()>1:
				canonical_er=voyage_enslavement_relations[0]
				other_ers=voyage_enslavement_relations[1:]
				for oer in other_ers:
					enslavers_in_relation=oer.relation_enslavers.all()
					for oeir in enslavers_in_relation:
						oeir.relation=canonical_er
						oeir.save()
					
		empty_count=0
		for er in EnslavementRelation.objects.all():
			if er.relation_enslavers.all().count()==0 and \
			er.enslaved_in_relation.all().count()==0:
				empty_count+=1
				er.delete()
		print("empty relations after rollup (now deleted)-->",empty_count)
			
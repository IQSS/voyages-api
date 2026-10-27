import csv
import re
from pyzotero import zotero
from django.core.management.base import BaseCommand, CommandError
from document.models import *
from past.models import *
from voyage.models import Voyage
import requests
import json
import os


class Command(BaseCommand):
	help = 'puts aliases behind identities'
	def handle(self, *args, **options):
		enslaverIdentities=EnslaverIdentity.objects.all()
		for enslaver_identity in enslaverIdentities:
			enslaverAliases=enslaver_identity.aliases.all()
			enslaver_voyage_ids=[]
			for enslaver_alias in enslaverAliases:
				enslaverRelations=enslaver_alias.enslaver_relations.all()
				for enslaver_relation in enslaverRelations:
					roles=[r[0] for r in enslaver_relation.roles.all().values_list('name')]
					if 'Captain' in roles or 'Investor' in roles:
						enslaver_voyage_id=enslaver_relation.relation.voyage.voyage_id
						if enslaver_voyage_id is not None:
							enslaver_voyage_ids.append(enslaver_voyage_id)
			enslaver_voyage_ids=list(set(enslaver_voyage_ids))
			enslaver_voyage_annotated_queryset=Voyage.objects.all().filter(voyage_id__in=enslaver_voyage_ids).annotate(total_enslaved=Sum('voyage_slaves_numbers__imp_total_num_slaves_embarked'))
			total_enslaved=sum([i[0] for i in enslaver_voyage_annotated_queryset.values_list('total_enslaved') if i[0] is not None])
			if total_enslaved > 0:
# 				print(enslaver_identity,total_enslaved)
				enslaver_identity.number_enslaved_people=total_enslaved
				enslaver_identity.save()

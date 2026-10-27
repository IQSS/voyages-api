import csv
import re
from pyzotero import zotero
from django.core.management.base import BaseCommand, CommandError
from document.models import *
from past.models import *
from doc.models import *
from voyage.models import *
from voyages3.settings import *
import requests
import json
import os

# the current past organization is just awful to deal with. we need to
## 1) put aliases behind identities
## 2) attach voyages, relations, and sources directly to identities instead of aliases
## 3) route voyages through relations as a transportation relation w/ captain or shipowner role

## down the line we need to allow for multiple roles in a single relation
#### and then merge the duplicates (where the same enslaver & enslaved are connected but under different roles)

class Command(BaseCommand):
	help = 'puts aliases behind identities'
	def handle(self, *args, **options):
		aliases=EnslaverAlias.objects.all()
		for a in aliases:
			a2,a2_isnew=EnslaverAlias.objects.get_or_create(
				manual_id=a.manual_id,
				last_updated=a.last_updated,
				human_revieweda.human_reviewed,
				identity=a.identity,
				alias=a.alias
			)
		
		enslaverinrelations=EnslaverInRelation.objects.all()
		for eir in enslaverinrelations:
			eir.enslaver_identity2=eir.enslaver_alias.identity
			eir.save()
		

import requests
import json
import time
import numpy as np
from itertools import islice
from django.core.management.base import BaseCommand, CommandError
from voyage.models import *

coded_obj_classes={
'RigOfVessel.tsv':RigOfVessel,
'Nationality.tsv':Nationality,
'ParticularOutcome.tsv':ParticularOutcome,
'SlavesOutcome.tsv':SlavesOutcome,
'OwnerOutcome.tsv':OwnerOutcome,
'VesselCapturedOutcome.tsv':VesselCapturedOutcome,
'Resistance.tsv':Resistance,
'RigOfVessel.tsv':RigOfVessel
}


class Command(BaseCommand):
	help = 'pushes canonical voyages value codes'
	def handle(self, *args, **options):
		for co_class_filename in coded_obj_classes:
			d=open('voyage/management/commands/codedclasses/'+co_class_filename,'r')
			t=d.read()
			d.close()
			lines=[l for l in t.split('\n') if l!='']
			
			thisclass=coded_obj_classes[co_class_filename]
			for line in lines:
				print(line)
				thisclass.objects.all().delete()
				id,name,value=line.split('\t')
				thisobj=thisclass.objects.create(
					id=id,
					name=name,
					value=value
				)
				thisobj.save()


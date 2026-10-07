import csv
import re
from pyzotero import zotero
from django.core.management.base import BaseCommand, CommandError
from document.models import *
from past.models import *
from document.models import *
from voyage.models import *
from voyages3.settings import *
import requests
import json
import os



class Command(BaseCommand):
	help = 'before you run consolidate_enslavement_relations, run this'
	def handle(self, *args, **options):
		enslavementrelations=EnslavementRelation.objects.all()
		voyage_enslavementrelations=enslavementrelations.filter(is_from_voyages=True)
		print("all relations:",enslavementrelations.count())
		print("voyage_relations:",voyage_enslavementrelations.count())
# 		voyage_enslavementrelations.delete()

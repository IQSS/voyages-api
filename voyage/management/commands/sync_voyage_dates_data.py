
import requests
import json
import time
import numpy as np
from itertools import islice
from django.core.management.base import BaseCommand, CommandError
from voyage.models import *
from common.models import SparseDate

class Command(BaseCommand):
	help = 'Maps all comma-spliced voyage fields to their new counterparts'
	def handle(self, *args, **options):

###### SHARED BETWEEN METHODS 1 & 2
##### BOTH OF WHICH TRY TO USE THE BATCH SETTINGS IN DJANGO
##### WITH A HAND-MADE NUMPY BINNER TO BATCH THE JOB
##### I ATTEMPTED TO USE THE ASYNC BATCH AND THE REGULAR BATCH SETTINGS IN DJANGO
######## BUT I COULDN'T GET THE CHANGES TO TAKE WITH EITHER OF THOSE
		voyagedates=VoyageDates.objects.all()
		st=time.time()
# 		SparseDate.objects.all().delete()
# 		delete_time=time.time()-st
# 		print("deleted sparse date objects in %d seconds" %delete_time)
		
		
		vd1=voyagedates[0]
		process_st=time.time()
		excluded_fields=['id']
		vdfields=[i for i in list(vd1.__dict__.keys()) if i.endswith('_id') and not i=='voyage_id' and i not in excluded_fields]
		print("vdfields---->",vdfields)
		
		#METHOD 1 -- "LONG" - FIELD BY FIELD OVER ALL 60K+ VOYAGES
		#FINISHES IN ~280 seconds
		batch_size=2500
		print("number of fields:",len(vdfields))
		for vdfield in vdfields:
			field_st=time.time()
			voyagedate_objs=[]
			print("vdfield-->",vdfield)
			nonsparsefieldname=vdfield.replace('_sparsedate_id','')
			for vd in voyagedates:
				vdval=eval("vd.%s" %nonsparsefieldname)
				if "," in str(vdval):
					m,d,y=[int(i) if i!='' else None for i in vdval.split(',')]
					sd,sd_isnew=SparseDate.objects.get_or_create(
						day=d,
						month=m,
						year=y
					)
					exec('vd.'+vdfield+'=sd.id')
				else:
					sd=None
					exec('vd.'+vdfield+'=None')
				voyagedate_objs.append(vd)
			c=1
			batches=np.array_split(voyagedate_objs,len(voyagedate_objs)/batch_size)
			for batch in batches:
				st_slice=time.time()
				VoyageDates.objects.bulk_update(batch,[vdfield])
			print("field finished in %d seconds" %(time.time()-field_st))
		print("full job finished in %d seconds" %(time.time()-process_st))
		
# 		#METHOD 1 -- "WIDE" - ALL FIELDS, VOYAGE-BY-VOYAGE
# 		#FINISHES IN ~350 seconds
# 		voyagedate_objs=[]
# 		batch_size=2500
# 		print("number of VOYAGEDATES:",len(voyagedates))
# 		for vd in voyagedates:
# 			for vdfield in vdfields:
# 				nonsparsefieldname=vdfield.replace('_sparsedate_id','')
# 				vdval=eval("vd.%s" %nonsparsefieldname)
# 				if "," in str(vdval):
# 					m,d,y=[int(i) if i!='' else None for i in vdval.split(',')]
# 					sd=SparseDate.objects.create(
# 						day=d,
# 						month=m,
# 						year=y
# 					)
# 					exec('vd.'+vdfield+'=sd.id')
# 				else:
# 					sd=None
# 					exec('vd.'+vdfield+'=None')
# 			voyagedate_objs.append(vd)
# 		batches=np.array_split(voyagedate_objs,len(voyagedate_objs)/batch_size)
# 		for batch in batches:
# 			st_slice=time.time()
# 			VoyageDates.objects.bulk_update(batch,vdfields)
# 			print("batch finished in %d seconds" %(time.time()-st_slice))
# 		print("full job finished in %d seconds" %(time.time()-process_st))


##### METHOD 3 (ORIGINAL) Does not batch.
		#FINISHES IN ~327 seconds
# 		voyages=Voyage.objects.all()
# 
# 		st=time.time()
# 		for v in voyages:
# # 			print(v)
# 			vd=v.voyage_dates
# 			vdfields=[i for i in list(vd.__dict__.keys()) if i not in ('_state','id') and not i.endswith('_id')]
# 			
# 			for vdfield in vdfields:
# 				vdval=eval('vd.'+vdfield)
# 				if "," in str(vdval):
# 					m,d,y=[int(i) if i!='' else None for i in vdval.split(',')]
# # 					print(vdfield,[m,d,y])
# 					sd=SparseDate.objects.create(
# 						day=d,
# 						month=m,
# 						year=y
# 					)
# # 					print(sd)
# 					exec('vd.'+vdfield+'_sparsedate=sd')
# 			vd.save()
# # 			print(vd)
# 		print("now",time.time())
# 		print("start",st)
# 		print("completed in %d seconds" %(time.time()-st))

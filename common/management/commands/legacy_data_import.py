import mysql.connector
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
	help = 'publishes the schema as flat json and python files, \
	which are used to populate the options avaiable in the model serializers. \
	this should be run any time you alter the serializers or models. \
	outputs go to api/common/static and are included in the git repo.'
	def handle(self, *args, **options):
		
		print(Source.objects.all().count(), "total sources")
		def intornone(i):
			try:
				return int(i)
			except:
				return None


		cnx = mysql.connector.connect(
			host="voyages-mysql",
			port=3306,
			user="root",
			password="voyages",
			database="voyages_legacy")
			
		cur = cnx.cursor()

		#validate connection
# 		result = cur.execute("SELECT * FROM voyage_voyage LIMIT 1")
# 		row = cur.fetchone()
# 		
# 		# VOYAGE GROUPINGS
# 		# so the way I set up the new system is to have voyages be where all the other tables point to
# 		# except in the case of the obscure "voyage groupings" table
# 		
# 		result=cur.execute("SELECT id,label,value from voyage_voyagegroupings;")
# 		
# 		# VALUE field is the spss permanent key
# 		# overwrite api data
# 		# "label" field has been renamed to "name" field
# 		voyage_grouping_pk_map={}
# 		for row in cur.fetchall():
# 			id,label,value=row
# 			vg,vg_isnew=VoyageGroupings.objects.get_or_create(
# 				value=value
# 			)
# 			vg.name=label
# 			voyage_grouping_pk_map[id]=vg.id
# 			vg.save()
# 		
# 		d=open('voyage_grouping_pk_map.json','w')
# 		d.write(json.dumps(voyage_grouping_pk_map))
# 		d.close
# 		
# 		# CRUCIAL SPSS TABLES
# 		
# 		## GEO
# 		print("geo")
# 		def location_get_create_or_update(name,longitude,latitude,value):
# 			try:
# 				location=Location.objects.get(value=value)
# 			except:
# 				location=None
# 			
# 			if not location:
# 				location=Location.objects.create(
# 					name=name,
# 					longitude=longitude,
# 					latitude=latitude,
# 					value=value
# 				)
# 			else:
# 				location.name=name
# 				location.longitude=longitude
# 				location.latitude=latitude
# 				location.value=value
# 				location.save()
# 			return location
# 
# 		## got to do them in this order because it's 3 hierarchical tables in legacy
# 		
# 		### voyage_broadregion
# 		broad_region_id_map={}
# 		result=cur.execute("SELECT \
# 			id,\
# 			broad_region,\
# 			longitude,\
# 			latitude,\
# 			value\
# 		from voyage_broadregion;")
# 		
# 		loc_type=LocationType.objects.get(name="Broad Region")
# 		for row in cur.fetchall():
# 			id,name,longitude,latitude,value=row
# 			location=location_get_create_or_update(name,longitude,latitude,value)
# 			location.location_type=loc_type
# 			location.save()
# 			broad_region_id_map[id]=location.id
# 			
# 		d=open('broad_region_id_map.json','w')
# 		d.write(json.dumps(broad_region_id_map))
# 		d.close
# 		
# 		### voyage_region
# 		
# 		result=cur.execute("SELECT \
# 			id,\
# 			region,\
# 			broad_region_id,\
# 			longitude,\
# 			latitude,\
# 			value\
# 		from voyage_region;")
# 		region_id_map={}
# 		loc_type=LocationType.objects.get(name="Region")
# 		for row in cur.fetchall():
# 			id,name,broad_region_id,longitude,latitude,value=row
# 			location=location_get_create_or_update(name,longitude,latitude,value)
# 			broad_region=Location.objects.get(id=broad_region_id_map[broad_region_id])
# 			location.broad_region=broad_region
# 			location.location_type=loc_type
# 			location.save()
# 			region_id_map[id]=location.id
# 
# 		d=open('region_id_map.json','w')
# 		d.write(json.dumps(region_id_map))
# 		d.close
# 
# 		### voyage_place
# 		
# 		result=cur.execute("SELECT \
# 			id,\
# 			place,\
# 			region_id,\
# 			longitude,\
# 			latitude,\
# 			value\
# 		from voyage_place;")
# 		place_id_map={}
# 		loc_type=LocationType.objects.get(name="Place")
# 		for row in cur.fetchall():
# 			id,name,region_id,longitude,latitude,value=row
# 			location=location_get_create_or_update(name,longitude,latitude,value)
# 			region=Location.objects.get(id=region_id_map[region_id])
# 			location.region=region
# 			location.location_type=loc_type
# 			location.save()
# 			place_id_map[id]=location.id
# 		
# 		d=open('place_id_map.json','w')
# 		d.write(json.dumps(place_id_map))
# 		d.close
# 		
# 		def spss_controlled_vocab(
# 			model,
# 			table,
# 			cur,
# 			label_or_name='label',
# 			value_field=True
# 		):
# 			if value_field:
# 				result=cur.execute(f"SELECT \
# 					id,\
# 					{label_or_name},\
# 					value\
# 				from {table};")
# 				duplicate_map={}
# 				for row in cur.fetchall():
# 					id,name,value=row
# 					try:
# 						model.objects.create(
# 							id=id,
# 							name=name,
# 							value=value
# 						)
# 					except IntegrityError:
# 						print(
# 							row,
# 							"already exists. remapping to",
# 							model.objects.get(name=name).id
# 						)
# 						duplicate_map[id]=model.objects.get(name=name).id
# 			
# 			else:
# 				result=cur.execute(f"SELECT \
# 					id,\
# 					{label_or_name}\
# 				from {table};")
# 				
# 				for row in cur.fetchall():
# 					duplicate_map={}
# 					try:
# 						id,name=row
# 						model.objects.create(
# 							id=id,
# 							name=name
# 						)
# 					except IntegrityError:
# 						print(
# 							row,
# 							"already exists. remapping to",
# 							model.objects.get(name=name).id
# 						)
# 						duplicate_map[id]=model.objects.get(name=name).id
# 			return duplicate_map
# 				
# 		print("spss controlled vocabs")
# 		
# 		Nationality.objects.all().delete()
# 		spss_controlled_vocab(
# 			Nationality,
# 			'voyage_nationality',
# 			cur
# 		)
# 		
# 		TonType.objects.all().delete()
# 		spss_controlled_vocab(
# 			TonType,
# 			'voyage_tontype',
# 			cur
# 		)
# 		
# 		RigOfVessel.objects.all().delete()
# 		rigofvessel_id_map=spss_controlled_vocab(
# 			RigOfVessel,
# 			'voyage_rigofvessel',
# 			cur
# 		)
# 		
# 		ParticularOutcome.objects.all().delete()
# 		spss_controlled_vocab(
# 			ParticularOutcome,
# 			'voyage_particularoutcome',
# 			cur
# 		)
# 		
# 		SlavesOutcome.objects.all().delete()
# 		spss_controlled_vocab(
# 			SlavesOutcome,
# 			'voyage_slavesoutcome',
# 			cur
# 		)
# 		
# 		VesselCapturedOutcome.objects.all().delete()
# 		spss_controlled_vocab(
# 			VesselCapturedOutcome,
# 			'voyage_vesselcapturedoutcome',
# 			cur
# 		)
# 		
# 		OwnerOutcome.objects.all().delete()
# 		spss_controlled_vocab(
# 			OwnerOutcome,
# 			'voyage_owneroutcome',
# 			cur
# 		)
# 		
# 		Resistance.objects.all().delete()
# 		spss_controlled_vocab(
# 			Resistance,
# 			'voyage_resistance',
# 			cur
# 		)
# 		
# 		## those without spss codes
# 		print("non-spss controlled vocabs")
# 		
# 		CargoType.objects.all().delete()
# 		spss_controlled_vocab(
# 			CargoType,
# 			'voyage_cargotype',
# 			cur,
# 			label_or_name='name',
# 			value_field=False
# 		)
# 		
# 		CargoUnit.objects.all().delete()
# 		spss_controlled_vocab(
# 			CargoUnit,
# 			'voyage_cargounit',
# 			cur,
# 			label_or_name='name',
# 			value_field=False
# 		)
# 		
# 		AfricanInfo.objects.all().delete()
# 		spss_controlled_vocab(
# 			AfricanInfo,
# 			'voyage_africaninfo',
# 			cur,
# 			label_or_name='name',
# 			value_field=False
# 		)		
# 		
# 		#PURGE
# 		print("purging:---")
# 		print('VoyageSlavesNumbers')
# 		VoyageSlavesNumbers.objects.all().delete()
# 		print('VoyageSparseDate')
# 		VoyageSparseDate.objects.all().delete()
# 		print('LinkedVoyages')
# 		LinkedVoyages.objects.all().delete()
# 		print('VoyageItinerary')
# 		VoyageItinerary.objects.all().delete()
# 		print('VoyageDates')
# 		VoyageDates.objects.all().delete()
# 		print('VoyageOutcome')
# 		VoyageOutcome.objects.all().delete()
# 		print('VoyageShip')
# 		VoyageShip.objects.all().delete()
# 		print('Crew Numbers')
# 		VoyageCrew.objects.all().delete()
# 		
# 		# VOYAGES
# 		
# 		result=cur.execute("SELECT\
# 			id,\
# 			voyage_id,\
# 			voyage_in_cd_rom,\
# 			last_update,\
# 			dataset,\
# 			comments,\
# 			voyage_groupings_id\
# 		from voyage_voyage;")
# 		
# 		# VALUE field is the spss permanent key
# 		# overwrite api data
# 		voyage_pk_map={}
# 		utc=pytz.UTC
# 		
# 		vrs=[r for r in cur.fetchall()]
# 		for row in vrs:
# 			voyage_id_pk,voyage_id,voyage_in_cd_rom,last_update,dataset,comments,voyage_groupings_id=row
# 			if voyage_groupings_id is not None:
# 				voyage_groupings_id=voyage_grouping_pk_map[voyage_groupings_id]
# 				voyage_grouping=VoyageGroupings.objects.get(id=voyage_groupings_id)
# 			else:
# 				voyage_grouping=None
# 			
# 			last_update=utc.localize(last_update)
# 			
# 			try:
# 				v=Voyage.objects.get(voyage_id=voyage_id)
# 			except:
# 				v=None
# 			
# 			if not v:
# 				voyage_isnew=True
# 				#we should be able to keep pk & voyage_id aligned, as I was pretty careful about that...
# 				v=Voyage.objects.create(
# 					id=voyage_id,
# 					voyage_id=voyage_id,
# 					voyage_in_cd_rom=voyage_in_cd_rom,
# 					dataset=dataset,
# 					comments=comments,
# 					voyage_groupings=voyage_grouping
# 				)
# 			else:
# 				v.voyage_in_cd_rom=voyage_in_cd_rom
# 				v.dataset=dataset
# 				v.comments=comments
# 				v.voyage_groupings=voyage_grouping
# 				v.save()
# 				voyage_isnew=False
# 			
# 			print(v,v.id,v.voyage_id)
# 			
# 			# connect new voyages to existing sources
# 			
# 			if voyage_isnew:
# 				result=cur.execute(f"select * from voyage_voyagesourcesconnection left join voyage_voyagesources on voyage_voyagesources.id=voyage_voyagesourcesconnection.source_id where voyage_voyagesourcesconnection.group_id={v.id};")
# 				
# 				rows=[r for r in cur.fetchall()]
# 				
# 				for row in cur.fetchall():
# 					id, source_order,text_ref,group_id,source_id,short_ref,full_ref,source_type_id=row
# 					
# 					##### now fetch the source by the short ref in the api, and create a sourcevoyageconnection object. That's it!
# 					
# 			
# 			
# 			
# 			
# 			
# 			
# 			
# 			
# # 			### VOYAGE DATES
# 			
# 			result=cur.execute(f"SELECT\
# 				voyage_began,\
# 				slave_purchase_began,\
# 				vessel_left_port,\
# 				first_dis_of_slaves,\
# 				date_departed_africa,\
# 				arrival_at_second_place_landing,\
# 				third_dis_of_slaves,\
# 				departure_last_place_of_landing,\
# 				voyage_completed,\
# 				length_middle_passage_days,\
# 				imp_voyage_began,\
# 				imp_departed_africa,\
# 				imp_arrival_at_port_of_dis,\
# 				imp_length_home_to_disembark,\
# 				imp_length_leaving_africa_to_disembark,\
# 				voyage_id\
# 			from voyage_voyagedates where voyage_id={voyage_id_pk};")
# 			
# 			
# 			row=cur.fetchone()
# 			voyage_began, slave_purchase_began, vessel_left_port, first_dis_of_slaves, date_departed_africa, arrival_at_second_place_landing, third_dis_of_slaves, departure_last_place_of_landing, voyage_completed, length_middle_passage_days, imp_voyage_began, imp_departed_africa, imp_arrival_at_port_of_dis, imp_length_home_to_disembark, imp_length_leaving_africa_to_disembark,voyage_id=row
# 			vd=VoyageDates.objects.create(
# 				voyage=v,
# 				length_middle_passage_days=length_middle_passage_days,
# 				imp_length_home_to_disembark=imp_length_home_to_disembark,
# 				imp_length_leaving_africa_to_disembark=imp_length_leaving_africa_to_disembark
# 			)
# 			
# 			for vf in ['voyage_began', 'slave_purchase_began', 'vessel_left_port', 'first_dis_of_slaves', 'date_departed_africa', 'arrival_at_second_place_landing', 'third_dis_of_slaves', 'departure_last_place_of_landing', 'voyage_completed', 'imp_voyage_began', 'imp_departed_africa', 'imp_arrival_at_port_of_dis']:
# 				val=eval(vf)
# 				if val is not None:
# 					if len(val.split(','))==3:
# 						m,d,y=[intornone(i) for i in val.split(',')]
# 						sd=VoyageSparseDate.objects.create(month=m,day=d,year=y)
# 						sd.save()
# 						fstr=f"vd.{vf}_sparsedate=sd"
# 						exec(fstr)
# 				vd.save()
# 			
# 			### VOYAGE ITINERARIES
# 
# 			itinerary_var_types={
# 				'port_of_departure_id':'Place',
# 				'int_first_port_emb_id':'Place',
# 				'int_second_port_emb_id':'Place',
# 				'int_first_region_purchase_slaves_id':'Region',
# 				'int_second_region_purchase_slaves_id':'Region',
# 				'int_first_port_dis_id':'Place',
# 				'int_second_port_dis_id':'Place',
# 				'int_third_port_dis_id':'Place',
# 				'int_fourth_port_dis_id':'Place',
# 				'int_first_region_slave_landing_id':'Region',
# 				'int_second_place_region_slave_landing_id':'Region',
# 				'int_third_place_region_slave_landing_id':'Region',
# 				'int_fourth_place_region_slave_landing_id':'Region',
# 				'first_place_slave_purchase_id':'Place',
# 				'second_place_slave_purchase_id':'Place',
# 				'third_place_slave_purchase_id':'Place',
# 				'first_region_slave_emb_id':'Region',
# 				'second_region_slave_emb_id':'Region',
# 				'third_region_slave_emb_id':'Region',
# 				'port_of_call_before_atl_crossing_id':'Place',
# 				'first_landing_place_id':'Place',
# 				'second_landing_place_id':'Place',
# 				'third_landing_place_id':'Place',
# 				'first_landing_region_id':'Region',
# 				'second_landing_region_id':'Region',
# 				'third_landing_region_id':'Region',
# 				'place_voyage_ended_id':'Place',
# 				'region_of_return_id':'Region',
# 				'broad_region_of_return_id':'BroadRegion',
# 				'imp_port_voyage_begin_id':'Place',
# 				'imp_region_voyage_begin_id':'Region',
# 				'imp_broad_region_voyage_begin_id':'BroadRegion',
# 				'principal_place_of_slave_purchase_id':'Place',
# 				'imp_principal_place_of_slave_purchase_id':'Place',
# 				'imp_principal_region_of_slave_purchase_id':'Region',
# 				'imp_broad_region_of_slave_purchase_id':'BroadRegion',
# 				'principal_port_of_slave_dis_id':'Place',
# 				'imp_principal_port_slave_dis_id':'Place',
# 				'imp_principal_region_slave_dis_id':'Region',
# 				'imp_broad_region_slave_dis_id':'BroadRegion',
# 				'voyage_id':None
# 			}
# 			
# 			fstr=f"SELECT {','.join([k for k in itinerary_var_types])}\
# 				from voyage_voyageitinerary where voyage_id={voyage_id_pk};"
# 			result=cur.execute(fstr)
# 			
# 			row=cur.fetchone()
# 			
# 			vi=VoyageItinerary.objects.create(voyage=v)
# 		
# 			rowdict={list(itinerary_var_types)[i]:row[i] for i in range(len(itinerary_var_types))}
# 			for vit in itinerary_var_types:
# 				if vit!='voyage_id':
# 					vtype=itinerary_var_types[vit]
# 					vname=vit[:-3]
# 					loc_map={
# 						'Place':place_id_map,
# 						'Region':region_id_map,
# 						'BroadRegion':broad_region_id_map
# 					}[vtype]
# 					
# 					if vit!='voyage_id':
# 						loc_id=rowdict[vit]
# 						if loc_id is not None:
# 							loc_id=loc_map[loc_id]
# 							location=Location.objects.get(id=loc_id)
# 							exec(f"vi.{vname}=location")
# 				vi.save()
# 			
# 			### VOYAGE OUTCOMES
# 			
# 			
# 			vo=VoyageOutcome.objects.create(
# 				voyage=v
# 			)
# 			
# 			result=cur.execute(f"SELECT\
# 				outcome_owner_id,\
# 				outcome_slaves_id,\
# 				particular_outcome_id,\
# 				resistance_id,\
# 				vessel_captured_outcome_id,\
# 				voyage_id\
# 			from voyage_voyageoutcome where voyage_id={voyage_id_pk};")
# 
# 			row = cur.fetchone()
# 			owner_outcome_id, outcome_slaves_id,particular_outcome_id,resistance_id,vessel_captured_outcome_id,voyage_id=row
# 				
# 			if owner_outcome_id is not None:
# 				oo=OwnerOutcome.objects.get(id=owner_outcome_id)
# 				vo.owner_outcome=oo
# 			if outcome_slaves_id is not None:
# 				os=SlavesOutcome.objects.get(id=outcome_slaves_id)
# 				vo.outcome_slaves=os
# 			if particular_outcome_id is not None:	
# 				po=ParticularOutcome.objects.get(id=particular_outcome_id)
# 				vo.particular_outcome=po
# 			if resistance_id is not None:
# 				ro=Resistance.objects.get(id=resistance_id)
# 				vo.resistance=ro
# 			if vessel_captured_outcome_id is not None:
# 				vco=VesselCapturedOutcome.objects.get(id=vessel_captured_outcome_id)
# 				vo.vessel_captured_outcome=vco
# 			vo.save()
# 
# 			### VOYAGE SHIPS
# 			
# 			ship=VoyageShip.objects.create(
# 				voyage=v
# 			)
# 			
# 			result=cur.execute(f"SELECT\
# 				ship_name,\
# 				tonnage,\
# 				guns_mounted,\
# 				year_of_construction,\
# 				registered_year,\
# 				tonnage_mod,\
# 				imputed_nationality_id,\
# 				nationality_ship_id,\
# 				registered_place_id,\
# 				registered_region_id,\
# 				rig_of_vessel_id,\
# 				ton_type_id,\
# 				vessel_construction_place_id,\
# 				vessel_construction_region_id,\
# 				voyage_id\
# 			from voyage_voyageship where voyage_id={voyage_id_pk};")
# 			
# 			for row in cur.fetchall():
# 				ship_name,tonnage,guns_mounted,year_of_construction,registered_year,tonnage_mod,imputed_nationality_id,nationality_ship_id,registered_place_id,registered_region_id,rig_of_vessel_id,ton_type_id,vessel_construction_place_id,vessel_construction_region_id,voyage_id=row
# 				ship.ship_name=ship_name
# 				ship.tonnage=tonnage
# 				ship.guns_mounted=guns_mounted
# 				ship.year_of_construction=year_of_construction
# 				ship.registered_year=registered_year
# 				ship.tonnage_mod=tonnage_mod
# 				
# 				if nationality_ship_id is not None:
# 					nationality=Nationality.objects.get(id=nationality_ship_id)
# 					ship.imputed_nationality=nationality
# 				
# 				if imputed_nationality_id is not None:
# 					nationality=Nationality.objects.get(id=imputed_nationality_id)
# 					ship.imputed_nationality=nationality
# 				
# 				if registered_place_id is not None:
# 					registered_place_id=place_id_map[registered_place_id]
# 					registered_place=Location.objects.get(id=registered_place_id)
# 					ship.registered_place=registered_place
# 				
# 				if registered_region_id is not None:
# 					registered_region_id=region_id_map[registered_region_id]
# 					registered_region=Location.objects.get(id=registered_region_id)
# 					ship.registered_region=registered_region
# 				
# 				if rig_of_vessel_id is not None:
# 					if rig_of_vessel_id in rigofvessel_id_map:
# 						rig_of_vessel_id=rigofvessel_id_map[rig_of_vessel_id]
# 					rig_of_vessel=RigOfVessel.objects.get(id=rig_of_vessel_id)
# 					ship.rig_of_vessel=rig_of_vessel
# 				
# 				if ton_type_id is not None:
# 					ton_type=TonType.objects.get(id=ton_type_id)
# 					ship.ton_type=ton_type
# 				
# 				if vessel_construction_place_id is not None:
# 					vessel_construction_place_id=place_id_map[vessel_construction_place_id]
# 					construction_place=Location.objects.get(id=vessel_construction_place_id)
# 					ship.vessel_construction_place=construction_place
# 				
# 				if vessel_construction_region_id is not None:
# 					vessel_construction_region_id=region_id_map[vessel_construction_region_id]
# 					vessel_construction_region=Location.objects.get(id=vessel_construction_region_id)
# 					ship.vessel_construction_region=vessel_construction_region
# 					
# 				ship.save()
# 			
# 			
# # 			### LINKED VOYAGES
# 			
# 			
# 			
# 			result=cur.execute(f"SELECT second_id \
# 			from voyage_linkedvoyages where first_id={voyage_id_pk};")
# 			
# 			for row in cur.fetchall():
# 				linked_id=row[0]
# 				LinkedVoyages.objects.create(first_id=voyage_id_pk,second_id=linked_id)
# 			
# 			
# 			## CAPTIVE NUMBERS
# 			
# 			numbers_fields=[
# 				'slave_deaths_before_africa',
# 				'slave_deaths_between_africa_america',
# 				'num_slaves_intended_first_port',
# 				'num_slaves_intended_second_port',
# 				'num_slaves_carried_first_port',
# 				'num_slaves_carried_second_port',
# 				'num_slaves_carried_third_port',
# 				'total_num_slaves_purchased',
# 				'total_num_slaves_dep_last_slaving_port',
# 				'total_num_slaves_arr_first_port_embark',
# 				'num_slaves_disembark_first_place',
# 				'num_slaves_disembark_second_place',
# 				'num_slaves_disembark_third_place',
# 				'imp_total_num_slaves_embarked',
# 				'imp_total_num_slaves_disembarked',
# 				'imp_jamaican_cash_price',
# 				'imp_mortality_during_voyage',
# 				'num_men_embark_first_port_purchase',
# 				'num_women_embark_first_port_purchase',
# 				'num_boy_embark_first_port_purchase',
# 				'num_girl_embark_first_port_purchase',
# 				'num_adult_embark_first_port_purchase',
# 				'num_child_embark_first_port_purchase',
# 				'num_infant_embark_first_port_purchase',
# 				'num_males_embark_first_port_purchase',
# 				'num_females_embark_first_port_purchase',
# 				'num_men_died_middle_passage',
# 				'num_women_died_middle_passage',
# 				'num_boy_died_middle_passage',
# 				'num_girl_died_middle_passage',
# 				'num_adult_died_middle_passage',
# 				'num_child_died_middle_passage',
# 				'num_infant_died_middle_passage',
# 				'num_males_died_middle_passage',
# 				'num_females_died_middle_passage',
# 				'num_men_disembark_first_landing',
# 				'num_women_disembark_first_landing',
# 				'num_boy_disembark_first_landing',
# 				'num_girl_disembark_first_landing',
# 				'num_adult_disembark_first_landing',
# 				'num_child_disembark_first_landing',
# 				'num_infant_disembark_first_landing',
# 				'num_males_disembark_first_landing',
# 				'num_females_disembark_first_landing',
# 				'num_men_embark_second_port_purchase',
# 				'num_women_embark_second_port_purchase',
# 				'num_boy_embark_second_port_purchase',
# 				'num_girl_embark_second_port_purchase',
# 				'num_adult_embark_second_port_purchase',
# 				'num_child_embark_second_port_purchase',
# 				'num_infant_embark_second_port_purchase',
# 				'num_males_embark_second_port_purchase',
# 				'num_females_embark_second_port_purchase',
# 				'num_men_embark_third_port_purchase',
# 				'num_women_embark_third_port_purchase',
# 				'num_boy_embark_third_port_purchase',
# 				'num_girl_embark_third_port_purchase',
# 				'num_adult_embark_third_port_purchase',
# 				'num_child_embark_third_port_purchase',
# 				'num_infant_embark_third_port_purchase',
# 				'num_males_embark_third_port_purchase',
# 				'num_females_embark_third_port_purchase',
# 				'num_men_disembark_second_landing',
# 				'num_women_disembark_second_landing',
# 				'num_boy_disembark_second_landing',
# 				'num_girl_disembark_second_landing',
# 				'num_adult_disembark_second_landing',
# 				'num_child_disembark_second_landing',
# 				'num_infant_disembark_second_landing',
# 				'num_males_disembark_second_landing',
# 				'num_females_disembark_second_landing',
# 				'imp_num_adult_embarked',
# 				'imp_num_children_embarked',
# 				'imp_num_male_embarked',
# 				'imp_num_female_embarked',
# 				'total_slaves_embarked_age_identified',
# 				'total_slaves_embarked_gender_identified',
# 				'imp_adult_death_middle_passage',
# 				'imp_child_death_middle_passage',
# 				'imp_male_death_middle_passage',
# 				'imp_female_death_middle_passage',
# 				'imp_num_adult_landed',
# 				'imp_num_child_landed',
# 				'imp_num_male_landed',
# 				'imp_num_female_landed',
# 				'total_slaves_landed_age_identified',
# 				'total_slaves_landed_gender_identified',
# 				'total_slaves_dept_or_arr_age_identified',
# 				'total_slaves_dept_or_arr_gender_identified',
# 				'imp_slaves_embarked_for_mortality',
# 				'imp_num_men_total',
# 				'imp_num_women_total',
# 				'imp_num_boy_total',
# 				'imp_num_girl_total',
# 				'imp_num_adult_total',
# 				'imp_num_child_total',
# 				'imp_num_males_total',
# 				'imp_num_females_total',
# 				'percentage_men',
# 				'percentage_women',
# 				'percentage_boy',
# 				'percentage_girl',
# 				'percentage_male',
# 				'percentage_child',
# 				'percentage_adult',
# 				'percentage_female',
# 				'imp_mortality_ratio',
# 				'slave_deaths_between_arrival_and_sale',
# 				'child_ratio_among_embarked_slaves',
# 				'child_ratio_among_landed_slaves',
# 				'male_ratio_among_embarked_slaves',
# 				'male_ratio_among_landed_slaves',
# 				'percentage_boys_among_embarked_slaves',
# 				'percentage_boys_among_landed_slaves',
# 				'percentage_girls_among_embarked_slaves',
# 				'percentage_girls_among_landed_slaves',
# 				'percentage_men_among_embarked_slaves',
# 				'percentage_men_among_landed_slaves',
# 				'percentage_women_among_embarked_slaves',
# 				'percentage_women_among_landed_slaves',
# 				'total_slaves_by_age_gender_identified_among_landed',
# 				'total_slaves_by_age_gender_identified_departure_or_arrival',
# 				'total_slaves_embarked_age_gender_identified',
# 				'voyage_id'
# 			]
# 			
# 			fstr=f"SELECT \
# 				{','.join([f for f in numbers_fields])} \
# 				from voyage_voyageslavesnumbers where voyage_id={voyage_id_pk};"
# 			result=cur.execute(fstr)
# 			
# 			for row in cur.fetchall():
# 				exec(f"{','.join([f for f in numbers_fields])}=row")
# 				
# 				vn=VoyageSlavesNumbers.objects.create(voyage=v)
# 				
# 				for i in range(len(numbers_fields)):
# 					vnf=numbers_fields[i]
# 					val=eval("vnf")
# 					if vnf!='voyage_id':
# 						exec(f"vn.{vnf}={val}")
# 				vn.save()
# 			
# 			
# 			#VOYAGE CREW NUMBERS
# 			numbers_fields=[
# 				'crew_voyage_outset',
# 				'crew_departure_last_port',
# 				'crew_first_landing',
# 				'crew_return_begin',
# 				'crew_end_voyage',
# 				'unspecified_crew',
# 				'crew_died_before_first_trade',
# 				'crew_died_while_ship_african',
# 				'crew_died_middle_passage',
# 				'crew_died_in_americas',
# 				'crew_died_on_return_voyage',
# 				'crew_died_complete_voyage',
# 				'crew_deserted',
# 				'voyage_id'
# 			]
# 			
# 			fstr=f"SELECT \
# 				{','.join([f for f in numbers_fields])} \
# 				from voyage_voyagecrew where voyage_id={voyage_id_pk};"
# 			result=cur.execute(fstr)
# 			
# 			for row in cur.fetchall():
# 				exec(f"{','.join([f for f in numbers_fields])}=row")
# 				
# 				vcn=VoyageCrew.objects.create(voyage=v)
# 				
# 				for i in range(len(numbers_fields)):
# 					vnf=numbers_fields[i]
# 					val=eval("vnf")
# 					if vnf!='voyage_id':
# 						exec(f"vcn.{vnf}={val}")
# 				vcn.save()
# 			v=Voyage.objects.get(id=voyage_id_pk)
# 			if v.id!=v.voyage_id:
# 				print("pk and voyage id don't match",v,v.id,v.voyage_id)
# 				exit()
# 		
# 		#PAST
# 		
# 		print("purging past entities")
# 		print("purging enslaveridentities")
# 		EnslaverIdentity.objects.all().delete()
# 		print("purging enslaveraliases")
# 		EnslaverAlias.objects.all().delete()
# 		print("purging enslaved")
# 		Enslaved.objects.all().delete()
# 		print("purging enslavementrelations")
# 		EnslavementRelation.objects.all().delete()
# 		print("purging pastsparsedates")
# 		PASTSparseDate.objects.all().delete()
# 		
# 		#ENSLAVERS
# 		print("creating enslaver records")
# 		enslaver_fields=[
# 			'id',
# 			'principal_alias',
# 			'birth_year',
# 			'birth_month',
# 			'birth_day',
# 			'birth_place_id',
# 			'death_year',
# 			'death_month',
# 			'death_day',
# 			'death_place_id',
# 			'father_name',
# 			'father_occupation',
# 			'mother_name',
# 			'probate_date',
# 			'will_value_pounds',
# 			'will_value_dollars',
# 			'will_court',
# 			'principal_location_id',
# 			'notes'
# 		]
# 		
# 
# 		fstr=f"SELECT \
# 			{','.join([f for f in enslaver_fields])} \
# 			from past_enslaveridentity;"
# 		result=cur.execute(fstr)
# 		
# 		for row in cur.fetchall():
# 			id,principal_alias,birth_year,birth_month,birth_day,birth_place_id,death_year,death_month,death_day,death_place_id,father_name,father_occupation,mother_name,probate_date,will_value_pounds,will_value_dollars,will_court,principal_location_id,notes=row
# 			
# 			enslaver_identity=EnslaverIdentity.objects.create(
# 				id=id,
# 				principal_alias=principal_alias,
# 				birth_year=birth_year,
# 				birth_month=birth_month,
# 				birth_day=birth_day,
# 				death_year=death_year,
# 				death_month=death_month,
# 				death_day=death_day,
# 				father_name=father_name,
# 				father_occupation=father_occupation,
# 				mother_name=mother_name,
# 				probate_date=probate_date,
# 				will_value_pounds=will_value_pounds,
# 				will_value_dollars=will_value_dollars,
# 				will_court=will_court,
# 				notes=notes
# 			)
# 
# 			if birth_place_id is not None:
# 				birth_place=Location.objects.get(id=place_id_map[birth_place_id])
# 				enslaver_identity.birth_place=birth_place
# 			
# 			if death_place_id is not None:
# 				death_place=Location.objects.get(id=place_id_map[death_place_id])
# 				enslaver_identity.death_place=death_place
# 			
# 			if principal_location_id is not None:
# 				principal_location=Location.objects.get(
# 					id=place_id_map[principal_location_id]
# 				)
# 				enslaver_identity.principal_location=principal_location
# 			
# 			enslaver_identity.save()
# 			
# # 			print(enslaver_identity)
# 
# 			
# 		enslaver_fields=[
# 			'id',
# 			'alias',
# 			'identity_id',
# 			'manual_id'
# 		]
# 		
# 
# 		fstr=f"SELECT \
# 			{','.join([f for f in enslaver_fields])} \
# 			from past_enslaveralias;"
# 		result=cur.execute(fstr)
# 		
# 		for row in cur.fetchall():
# 			id,alias,identity_id,manual_id=row
# 			
# 			enslaver_identity=EnslaverIdentity.objects.get(id=identity_id)
# 			
# 			enslaver_alias=EnslaverAlias.objects.create(
# 				id=id,
# 				alias=alias,
# 				identity=enslaver_identity
# 			)	
# # 			print(enslaver_alias)
# 		
# 		
# 		
# # 		## ENSLAVED
# 		
# 		fstr=f"select id,name,longitude,latitude from past_languagegroup"
# 		result=cur.execute(fstr)
# 		LanguageGroup.objects.all().delete()
# 		for row in cur.fetchall():
# 			id,name,longitude,latitude=row
# 			LanguageGroup.objects.create(
# 				id=id,
# 				name=name,
# 				longitude=longitude,
# 				latitude=latitude
# 			)
# 		
# 		fstr=f"select id,name,longitude,latitude from past_moderncountry"
# 		result=cur.execute(fstr)
# 		ModernCountry.objects.all().delete()
# 		for row in cur.fetchall():
# 			id,name,longitude,latitude=row
# 			ModernCountry.objects.create(
# 				id=id,
# 				name=name,
# 				longitude=longitude,
# 				latitude=latitude
# 			)
# 		
# 		register_country_id_map={}
# 		fstr=f"select id,name from past_registercountry"
# 		result=cur.execute(fstr)
# 		RegisterCountry.objects.all().delete()
# 		for row in cur.fetchall():
# 			id,name=row
# 			try:
# 				RegisterCountry.objects.create(
# 					id=id,
# 					name=name
# 				)
# 				register_country_id_map[id]=id
# 			except:
# 				#we have a duplicate entry problem
# 				register_country_id_map[id]=RegisterCountry.objects.get(name=name).id
# 		
# 		fstr=f"select id,name from past_captivefate"
# 		result=cur.execute(fstr)
# 		CaptiveFate.objects.all().delete()
# 		for row in cur.fetchall():
# 			id,name=row
# 			CaptiveFate.objects.create(
# 				id=id,
# 				name=name
# 			)
# 
# 		fstr=f"select id,name from past_captivestatus"
# 		result=cur.execute(fstr)
# 		CaptiveStatus.objects.all().delete()
# 		for row in cur.fetchall():
# 			id,name=row
# 			CaptiveStatus.objects.create(
# 				id=id,
# 				name=name
# 			)
# 
# 		fstr=f"select moderncountry_id,languagegroup_id from past_moderncountry_languages"
# 		result=cur.execute(fstr)
# 		for row in cur.fetchall():
# 			moderncountry_id,languagegroup_id=row
# 			language_group=LanguageGroup.objects.get(id=languagegroup_id)
# 			modern_country=ModernCountry.objects.get(id=moderncountry_id)
# 			modern_country.languages.add(language_group)
# 			modern_country.save()
# 		
# 		enslaved_fields=[
# 			'enslaved_id',
# 			'documented_name',
# 			'name_first',
# 			'name_second',
# 			'name_third',
# 			'modern_name',
# 			'editor_modern_names_certainty',
# 			'age',
# 			'height',
# 			'skin_color',
# 			'dataset',
# 			'notes',
# 			'captive_fate_id',
# 			'captive_status_id',
# 			'language_group_id',
# 			'last_known_date',
# 			'post_disembark_location_id',
# 			'register_country_id',
# 			'gender'
# 		]		
# 		
# 		fstr=f"SELECT \
# 			{','.join([f for f in enslaved_fields])} \
# 			from past_enslaved;"
# 		result=cur.execute(fstr)
# 		
# 		Gender.objects.all().delete()
# 		past_genders=[(1,"Male"),(2,"Female")]
# 		for pg in past_genders:
# 			id,name=pg
# 			Gender.objects.create(id=id,name=name)
# 		
# 		print("creating enslaved people records")
# 		for row in cur.fetchall():
# 			enslaved_id, documented_name, name_first, name_second, name_third, modern_name, editor_modern_names_certainty, age, height, skin_color, dataset, notes, captive_fate_id, captive_status_id, language_group_id, last_known_date, post_disembark_location_id, register_country_id, gender=row
# 			
# 			fks=[
# 				'captive_fate_id',
# 				'captive_status_id',
# 				'language_group_id',
# 				'last_known_date',
# 				'post_disembark_location_id',
# 				'register_country_id',
# 				'gender',
# 				'enslaved_id'
# 			]
# 
# 			straight_fields=[k for k in enslaved_fields if k not in fks]
# 			
# 			enslaved=Enslaved.objects.create(
# 				id=enslaved_id,
# 				enslaved_id=enslaved_id,
# 				documented_name=documented_name,
# 				name_first=name_first,
# 				name_second=name_second,
# 				name_third=name_third,
# 				modern_name=modern_name,
# 				editor_modern_names_certainty=editor_modern_names_certainty,
# 				age=age,
# 				height=height,
# 				skin_color=skin_color,
# 				dataset=dataset,
# 				notes=notes
# 			)
# 			
# 			if captive_fate_id:
# 				captive_fate=CaptiveFate.objects.get(id=captive_fate_id)
# 				enslaved.captive_fate=captive_fate
# 			
# 			if captive_status_id:
# 				captive_status=CaptiveStatus.objects.get(id=captive_status_id)
# 				enslaved.captive_status=captive_status
# 			
# 			if language_group_id:
# 				language_group=LanguageGroup.objects.get(id=language_group_id)
# 				enslaved.language_group=language_group
# 			
# 			if last_known_date:
# 				m,d,y=[intornone(i) for i in last_known_date.split(',')]
# 				sd=PastSparseDate.objects.create(month=m,day=d,year=y)
# 				enslaved.last_known_date=sd
# 			
# 			if post_disembark_location_id:
# 				post_disembark_location=Location.objects.get(
# 					id=place_id_map[post_disembark_location_id]
# 				)
# 				enslaved.post_disembark_location=post_disembark_location
# 			
# 			if register_country_id:
# 				register_country=RegisterCountry.objects.get(
# 					id=register_country_id_map[register_country_id]
# 				)
# 				enslaved.register_country=register_country
# 			
# 			if gender:
# 				gender_obj=Gender.objects.get(id=gender)
# 				enslaved.gender=gender_obj
# 			
# 			enslaved.save()
# 
# 		## SOURCES
# 		
# 		fstr="SELECT id,group_id,group_name from voyage_voyagesourcestype;"
# 		result=cur.execute(fstr)
# 		source_type_id_map={}
# 		for row in cur.fetchall():
# 			id,group_id,group_name=row
# 			st,st_isnew=SourceType.objects.get_or_create(
# 				name=group_name
# 			)
# 			print(id,st.id)
# 			source_type_id_map[id]=st.id
# 			
# 		
# 		fstr=f"SELECT id,short_ref,full_ref,source_type_id from voyage_voyagesources;"
# 		result=cur.execute(fstr)
# 		new_sources=0
# 		existing_sources=0
# 		
# 		print(f"creating sources. currently {Source.objects.all().count()} records")
# 		
# 		new_source_id_map={}
# 		for row in cur.fetchall():
# 			id,short_ref,full_ref,source_type_id=row
# 			source_type=SourceType.objects.get(id=source_type_id_map[source_type_id])
# 			short_ref,short_ref_isnew=ShortRef.objects.get_or_create(name=short_ref)
# 			if short_ref_isnew:
# 				source=Source.objects.create(
# 					short_ref=short_ref,
# 					source_type=source_type,
# 					title=full_ref,
# 					zotero_item_id="JULY2025IMPORT"
# 				)
# 				new_sources+=1
# 				new_source_id_map[id]=source.id
# 			else:
# 				existing_sources+=1
# 		print(f"sources finished. now {Source.objects.all().count()} records")
# 		
# 		new_source_id_map={13759: 19565, 13886: 19566, 14011: 19567, 14699: 19568, 15290: 19569, 15291: 19570, 15292: 19571, 15293: 19572, 15294: 19573, 15295: 19574, 15296: 19575, 15297: 19576, 15298: 19577, 15299: 19578, 15300: 19579, 15301: 19580, 15304: 19581, 15305: 19582, 15306: 19583, 15307: 19584, 15308: 19585, 15309: 19586, 15310: 19587, 15311: 19588, 15312: 19589, 15313: 19590, 15314: 19591, 15315: 19592, 15316: 19593, 15317: 19594, 15318: 19595, 15319: 19596, 15320: 19597, 15321: 19598, 15322: 19599, 15323: 19600, 15324: 19601, 15325: 19602, 15326: 19603, 15327: 19604, 15328: 19605, 15329: 19606, 15330: 19607, 15331: 19608, 15332: 19609, 15333: 19610, 15334: 19611, 15335: 19612, 15336: 19613, 15337: 19614, 15338: 19615, 15339: 19616, 15340: 19617, 15341: 19618, 15342: 19619, 15343: 19620, 15344: 19621, 15345: 19622, 15346: 19623, 15347: 19624, 15348: 19625, 15349: 19626, 15350: 19627, 15351: 19628, 15352: 19629, 15353: 19630, 15354: 19631, 15355: 19632, 15356: 19633, 15357: 19634, 15358: 19635, 15359: 19636, 15360: 19637, 15361: 19638, 15363: 19639, 15364: 19640, 15365: 19641, 15366: 19642, 15367: 19643, 15369: 19644, 15370: 19645, 15371: 19646, 15372: 19647, 15373: 19648, 15374: 19649, 15375: 19650, 15376: 19651, 15378: 19652, 15380: 19653, 15381: 19654, 15382: 19655, 15383: 19656, 15384: 19657, 15385: 19658, 15386: 19659, 15387: 19660, 15388: 19661, 15389: 19662, 15390: 19663, 15391: 19664, 15392: 19665, 15393: 19666, 15394: 19667, 15395: 19668, 15396: 19669, 15397: 19670, 15398: 19671}
# 
# 		##### JOIN THEM
# 		
# 		## Enslavers to Sources
# 		
# 		print("linking enslavers to sources")
# 		
# 		fstr=f"SELECT id,\
# 			text_ref,\
# 			identity_id,\
# 			source_id\
# 			from past_enslaveridentitysourceconnection;"
# 		result=cur.execute(fstr)
# 		new_sources=0
# 		existing_sources=0
# 		
# 		failures=0
# 		for row in cur.fetchall():
# 			id,text_ref,identity_id,source_id=row
# 			if source_id in new_source_id_map:
# 				source_id=new_source_id_map[source_id]
# 				source=Source.objects.get(id=source_id)
# 				enslaver=EnslaverIdentity.objects.get(id=identity_id)
# 				SourceEnslaverConnection.objects.create(
# 					source=source,
# 					enslaver=enslaver,
# 					page_range=text_ref[:249]
# 				)
# 
# 
# 
# 		#Fill in all missing source connections (but note, this treats short_ref as a unique field -- which is not true in 3 outlier cases and with all our new iiif docs)
# 		
# 		print('filling in voyage enslaver connections')
# 		result=cur.execute(f"select * from past_enslaveridentitysourceconnection\
# 			left join voyage_voyagesources on \
# 			voyage_voyagesources.id = \
# 			past_enslaveridentitysourceconnection.source_id ;"
# 		)
# 		
# 		for row in cur.fetchall():
# 			id, source_order,text_ref,enslaver_identity_id,source_id,source_id2,short_ref,full_ref,source_type_id=row
# 			print(row)
# 			ei=EnslaverIdentity.objects.get(id=enslaver_identity_id)
# 			sources=Source.objects.all().filter(short_ref__name=short_ref)
# 			if sources.count()>1:
# 				print(f"short ref {short_ref} has more than one source: {sources}")
# 				#now get the api source corresponding to that short ref
# 			elif sources.count()>0:
# 				source=sources[0]
# 				source_enslaver_connections=\
# 				source.source_enslaver_connections.all().filter(
# 					enslaver=ei
# 				)
# 				if source_enslaver_connections.count()==0:
# 					print(f"{ei} new to {short_ref}")
# 					SourceEnslaverConnection.objects.create(
# 						source=source,
# 						enslaver=ei,
# 						page_range=text_ref[:249]
# 					)
# 			else:
# 				short_ref,short_ref_isnew=ShortRef.objects.get_or_create(
# 					name=short_ref
# 				)
# 				source_type=SourceType.objects.get(id=source_type_id)
# 				source=Source.objects.create(
# 					title=full_ref,
# 					short_ref=short_ref,
# 					zotero_item_id="JULY2025IMPORT",
# 					source_type=source_type
# 				)
# 				sec=SourceEnslaverConnection.objects.create(
# 					page_range=text_ref,
# 					source=source,
# 					enslaver=ei
# 				)
# 				if short_ref_isnew:
# 					print("created short ref {short_ref}; source {source}; source enslaver connection {sec}")
# 				else:
# 					print("created source {source}; source enslaver connection {sec}; -- on short ref {short_ref}")
# 
# 
# 		
# 		## Voyages to Sources
# 		
# 		#Fill in all missing source connections (but note, this treats short_ref as a unique field -- which is not true in 3 outlier cases and with all our new iiif docs)
# 		
# 		print('filling in voyage source connections')
# 		result=cur.execute(f"select * from voyage_voyagesourcesconnection\
# 			left join voyage_voyagesources on \
# 			voyage_voyagesources.id = \
# 			voyage_voyagesourcesconnection.source_id ;"
# 		)
# 		
# 		for row in cur.fetchall():
# 			id, source_order,text_ref,voyage_id,source_id,source_id2,short_ref,full_ref,source_type_id=row
# 			print(short_ref)
# 			v=Voyage.objects.get(voyage_id=voyage_id)
# 			sources=Source.objects.all().filter(short_ref__name=short_ref)
# 			if sources.count()>1:
# 				print(f"short ref {short_ref} has more than one source: {sources}")
# 				#now get the api source corresponding to that short ref
# 			elif sources.count()>0:
# 				source=sources[0]
# 				
# 				source_voyage_connections=source.source_voyage_connections.all().filter(
# 					voyage=v
# 				)
# 				
# 				if source_voyage_connections.count()==0:
# 					print(f"{v} new to {short_ref}")
# 					SourceVoyageConnection.objects.create(
# 						page_range=text_ref,
# 						source=source,
# 						voyage=v
# 					)
# 			else:
# 				short_ref,short_ref_isnew=ShortRef.objects.get_or_create(
# 					name=short_ref
# 				)
# 				source_type=SourceType.objects.get(id=source_type_id)
# 				source=Source.objects.create(
# 					title=full_ref,
# 					short_ref=short_ref,
# 					zotero_item_id="JULY2025IMPORT",
# 					source_type=source_type
# 				)
# 				
# 				svc=SourceVoyageConnection.objects.create(
# 					page_range=text_ref,
# 					source=source,
# 					voyage=v
# 				)
# 				if short_ref_isnew:
# 					print("created short ref {short_ref}; source {source}; source voyage connection {svc}")
# 				else:
# 					print("created source {source}; source voyage connection {svc}; -- on short ref {short_ref}")
# 				
# 		
# 		## EnslavementRelations
# 		EnslavementRelation.objects.all().delete()
# 		EnslavementRelationType.objects.all().delete()
# 		
# 		print("creating enslavement relations")
# 		fstr=f"SELECT id,name from past_enslavementrelationtype;"
# 		result=cur.execute(fstr)
# 		
# 		for row in cur.fetchall():
# 			id,name=row
# 			EnslavementRelationType.objects.create(
# 				id=id,
# 				name=name
# 			)
# 		
# 		fstr=f"SELECT id,\
# 			relation_type_id,\
# 			voyage_id\
# 			from past_enslavementrelation;"
# 		result=cur.execute(fstr)
# 		
# 		fail=True
# 		for row in cur.fetchall():
# 			id,relation_type_id,voyage_id=row
# 			relation_type=EnslavementRelationType.objects.get(id=relation_type_id)
# 			fail=False
# 			try:
# 				voyage=Voyage.objects.get(id=voyage_id)
# 			except:
# 				voyage=None
# 			enslavement_relation=EnslavementRelation.objects.create(
# 				id=id,
# 				relation_type=relation_type,
# 				voyage=voyage
# 			)
# 		
# 		## EnslavedInRelation
# 		
# 		print("linking: ENSLAVED IN RELATION")
# 		EnslavedInRelation.objects.all().delete()
# 		
# 		fstr=f"SELECT \
# 			enslaved_id,\
# 			relation_id\
# 			from past_enslavedinrelation;"
# 		result=cur.execute(fstr)
# 		
# 		for row in cur.fetchall():
# 			enslaved_id,relation_id=row
# 			try:
# 				enslaved_in_relation=EnslavedInRelation.objects.create(
# 					enslaved_id=enslaved_id,
# 					relation_id=relation_id
# 				)
# 			except:
# 				print("failed on",row)
# 		
# 		print("linking: ENSLAVERS IN RELATION")
# 		EnslaverRole.objects.all().delete()
# 		enslaver_roles={
# 			1:'Captain',
# 			2:'Investor',
# 			3:'Buyer',
# 			4:'Seller',
# 			5:'Owner',
# 			6:'Shipper',
# 			7:'Consignor',
# 			8:'Spouse'
# 		}
# 		for enslaver_role_id in enslaver_roles:
# 			enslaver_role=enslaver_roles[enslaver_role_id]
# 			EnslaverRole.objects.create(
# 				id=enslaver_role_id,
# 				name=enslaver_role
# 			)
# 		
# 		EnslaverInRelation.objects.all().delete()
# 		fstr=f"SELECT \
# 			relation_id,\
# 			enslaver_alias_id,\
# 			role_id\
# 			from past_enslaverinrelation;"
# 		result=cur.execute(fstr)
# 		
# 		for row in cur.fetchall():
# 			try:
# 				relation_id,enslaver_alias_id,role_id=row
# 				relation=EnslavementRelation.objects.get(id=relation_id)
# 				enslaver_alias=EnslaverAlias.objects.get(id=enslaver_alias_id)
# 				if role_id in enslaver_roles:
# 					roles=[EnslaverRole.objects.get(id=role_id)]
# 				else:
# 					roles=EnslaverRole.objects.filter(name__in=['Investor','Captain'])
# 				
# 				
# 				enslaver_in_relation=EnslaverInRelation.objects.create(
# 					enslaver_alias=enslaver_alias,
# 					relation=relation
# 				)
# 				
# 				for role in roles:
# 					enslaver_in_relation.roles.add(role)
# 				enslaver_in_relation.save()
# 			except:
# 				print("failed on",row)
# 
# 
# 		## PEOPLE VOYAGE CONNECTIONS
# 		
# 		
# 		### OWNERS AND CAPTAINS
# 		
# 		print("TRANSPORTATION ENSLAVEMENT RELATIONS")
# 		
# 		fstr=f"SELECT \
# 			distinct voyage_id\
# 			from past_enslavervoyageconnection;"
# 		result=cur.execute(fstr)
# 		
# 		voyage_ids=list(set([i[0] for i in cur.fetchall()]))
# 		
# 		voyage_transportation_relations={}
# 		transportation_type=EnslavementRelationType.objects.get(name="Transportation")
# 		for v_id in voyage_ids:
# 			voyage=Voyage.objects.get(id=v_id)
# 			transportation_relation=EnslavementRelation.objects.create(
# 				relation_type=transportation_type,
# 				voyage=voyage
# 			)
# 			voyage_transportation_relations[voyage.id]=transportation_relation
# 		print("CONNECTING INVESTORS/CAPTAINS TO VOYAGES")
# 		fstr=f"SELECT \
# 			role_id,\
# 			enslaver_alias_id,\
# 			voyage_id\
# 			from past_enslavervoyageconnection;"
# 		result=cur.execute(fstr)
# 		
# 		for row in cur.fetchall():
# 			print(row)
# 			role_id,enslaver_alias_id,voyage_id=row
# 			transportation_relation=voyage_transportation_relations[voyage_id]
# 			if role_id in enslaver_roles:
# 				roles=[EnslaverRole.objects.get(id=role_id)]
# 			else:
# 				roles=EnslaverRole.objects.filter(name__in=['Investor','Captain'])
# 			enslaver_alias=EnslaverAlias.objects.get(id=enslaver_alias_id)
# 			enslaver_in_relation=EnslaverInRelation.objects.create(
# 				enslaver_alias=enslaver_alias,
# 				relation=transportation_relation
# 			)
# 			
# 			for role in roles:
# 				enslaver_in_relation.roles.add(role)
# 			enslaver_in_relation.save()
# 			
# 			
# 		### ENSLAVED
# 		
# 		print("CONNECTING ENSLAVED PEOPLE TO VOYAGES")
# 			
# 		fstr=f"SELECT \
# 			enslaved_id,\
# 			voyage_id\
# 			from past_enslaved;"
# 		result=cur.execute(fstr)
# 		print("CONNECTING ENSLAVED TO VOYAGES")
# 		for row in cur.fetchall():
# 			print(row)
# 			enslaved_id,voyage_id=row
# 			
# 			if voyage_id in voyage_transportation_relations:
# 				transportation_relation=voyage_transportation_relations[voyage_id]
# 			else:
# 				transportation_relation=EnslavementRelation.objects.create(
# 					relation_type=transportation_type,
# 					voyage=voyage
# 				)
# 				voyage_transportation_relations[voyage.id]=transportation_relation
# 			
# 			enslaved=Enslaved.objects.get(enslaved_id=enslaved_id)
# 			
# 			EnslavedInRelation.objects.create(
# 				enslaved=enslaved,
# 				relation=transportation_relation
# 			)
# 		
		
		### AND OF COURSE... SOME ENSLAVER DATA THAT SHOULD BE IN THE ENSLAVERS DB
		### IS STILL STUFFED IN THE CAPTAIN AND OWNER TABLES...
		### BUT THOSE TABLES ARE HIGHLY DUPLICATIVE WITH THE ENSLAVERS DATABASE
		
		print("IMPORT ENSLAVERS FROM LEGACY CAPTAIN AND OWNER TABLES")
		captain_and_shipowner_merges=[
			{
				"query":'select * from voyage_voyage left join \
			voyage_voyageshipownerconnection on \
			voyage_voyage.id=voyage_voyageshipownerconnection.voyage_id left join \
			voyage_voyageshipowner on \
			voyage_voyageshipownerconnection.owner_id=voyage_voyageshipowner.id \
			order by voyage_voyage.id;',
				"rolename":"Investor"
			},
			{
				"query":'select * from voyage_voyage left join \
			voyage_voyagecaptainconnection on \
			voyage_voyage.id=voyage_voyagecaptainconnection.voyage_id \
			left join voyage_voyagecaptain on \
			voyage_voyagecaptainconnection.captain_id=voyage_voyagecaptain.id;',
				"rolename":"Captain"
			}
		
		]
		new_enslaver_dict={}
		for captain_and_shipowner_merge in captain_and_shipowner_merges:
			rolename=captain_and_shipowner_merge['rolename']
			print(f"--->{rolename}s")
			query=captain_and_shipowner_merge['query']
			result=cur.execute(query)
			new_enslavers=0
			stopwords=['dos','das','fils','and']
			relation_type=EnslavementRelationType.objects.get(name="Transportation")
			role=EnslaverRole.objects.get(name=rolename)
			for row in cur.fetchall():
				id,voyage_id,voyage_in_cd_rom,voyage_crew_id,voyage_dates_id,\
					voyage_groupings_id,voyage_itinerary_id,voyage_ship_id,\
					voyage_slaves_numbers_id,last_update,dataset,comments,table2id,\
					owner_order,owner_id,voyage_id_table2,shipownerid,name=row
				if name not in [None,""]:
					fullname=name
					name=re.sub(r"\s*\*\s*"," ",name)
					name=re.sub(r"\s*\(.*?\)\s*"," ",name)
					name=re.sub("[.|\"|'|,|-|_]"," ",name)
					names=[n for n in name.split(" ") if n!="" and len(n)>2 and n.lower() not in stopwords]
					voyage=Voyage.objects.get(id=id)
					candidate_enslavers=EnslaverIdentity.objects.all().filter(
						aliases__enslaver_relations__relation__voyage__id=id
					)
					for name in names:
						if candidate_enslavers.count()!=0:
							candidate_enslavers=candidate_enslavers.filter(
								aliases__alias__icontains=name
							)
					if candidate_enslavers.count()==0:
						if fullname in new_enslaver_dict:
							enslaver_identity_id=new_enslaver_dict[fullname]
							enslaver_alias=enslaver_identity.aliases.first()
							enslavement_relation=EnslavementRelation.objects.create(
								voyage=voyage,
								relation_type=relation_type
							)
							enslaver_in_relation=EnslaverInRelation.objects.create(
								relation=enslavement_relation,
								enslaver_alias=enslaver_alias
							)
							enslaver_in_relation.roles.add(role)
							enslaver_in_relation.save()
						else:						
							print(voyage,"NEW-->",names)
							enslaver_identity=EnslaverIdentity.objects.create(
								principal_alias=fullname
							)
							enslaver_alias=EnslaverAlias.objects.create(
								identity=enslaver_identity,
								alias=fullname
							)
							enslavement_relation=EnslavementRelation.objects.create(
								voyage=voyage,
								relation_type=relation_type
							)
							enslaver_in_relation=EnslaverInRelation.objects.create(
								relation=enslavement_relation,
								enslaver_alias=enslaver_alias
							)
							enslaver_in_relation.roles.add(role)
							enslaver_in_relation.save()
							new_enslavers+=1
							new_enslaver_dict[fullname]=enslaver_identity.id
					else:
						enslaver_identity=candidate_enslavers.first()
						enslaver_in_relation=EnslaverInRelation.objects.all().filter(
							relation__voyage=voyage,
							enslaver_alias__identity=enslaver_identity
						).first()
						if role not in enslaver_in_relation.roles.all():
							enslaver_in_relation.roles.add(role)
							enslaver_in_relation.save()
					
			print(f"{new_enslavers} new {role.name}s")
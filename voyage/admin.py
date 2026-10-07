from django.contrib import admin
from voyage.models import *
from past.models import *
from document.models import *
import nested_admin
from common.models import *

class VoyageCrewInline(nested_admin.NestedStackedInline):
	model=VoyageCrew
	max_num=1
	classes = ['collapse']
	fields = [
		'crew_voyage_outset',
		'crew_died_complete_voyage'
	]
	verbose_name_plural="Voyage Crew"
	can_delete=False
	
class VoyageSparseDateAdmin(nested_admin.NestedModelAdmin):
	model=VoyageSparseDate
	max_num=1
	search_fields=['month','day','year']
	list_fields=['month','day','year']
	classes=['collapse']
	class Meta:
		fields='__all__'


class VoyageDatesInline(nested_admin.NestedStackedInline):
	model = VoyageDates
	max_num=1
	classes = ['collapse']
	autocomplete_fields = [
		'voyage_began_sparsedate',
		'slave_purchase_began_sparsedate',
		'vessel_left_port_sparsedate',
		'first_dis_of_slaves_sparsedate',
		'date_departed_africa_sparsedate',
		'arrival_at_second_place_landing_sparsedate',
		'third_dis_of_slaves_sparsedate',
		'departure_last_place_of_landing_sparsedate',
		'voyage_completed_sparsedate',
		'imp_voyage_began_sparsedate',
		'imp_departed_africa_sparsedate',
		'imp_arrival_at_port_of_dis_sparsedate'
	]
	can_delete=False
	
class VoyageSlavesNumbersInline(nested_admin.NestedTabularInline):
	model=VoyageSlavesNumbers
	classes = ['collapse']
	max_num=1
	can_delete=False

class ParticularOutcomeAdmin(admin.ModelAdmin):
	list_display = ('name','value')
	list_display_links = ('name',)
	model=ParticularOutcome
	search_fields=['name']
	classes = ['collapse']

class SlavesOutcomeAdmin(admin.ModelAdmin):
	list_display = ('name','value')
	list_display_links = ('name',)
	model=SlavesOutcome
	search_fields=['name']
	classes = ['collapse']
	
class VesselCapturedOutcomeAdmin(admin.ModelAdmin):
	list_display = ('name','value')
	list_display_links = ('name',)
	model=VesselCapturedOutcome
	search_fields=['name']
	classes = ['collapse']

class OwnerOutcomeAdmin(admin.ModelAdmin):
	list_display = ('name','value')
	list_display_links = ('name',)
	model=OwnerOutcome
	search_fields=['name']
	classes = ['collapse']

class ResistanceAdmin(admin.ModelAdmin):
	list_display = ('name','value')
	list_display_links = ('name',)
	model=Resistance
	search_fields=['name']
	classes = ['collapse']

class VoyageShipInline(nested_admin.NestedStackedInline):
	model = VoyageShip
	max_num = 1
	autocomplete_fields=(
		'vessel_construction_place',
		'vessel_construction_region',
		'registered_place',
		'registered_region'
	)
	classes = ['collapse']
	verbose_name_plural="Voyage Ship"

class VoyageItineraryInline(nested_admin.NestedStackedInline):
	model = VoyageItinerary
	max_num = 1
	autocomplete_fields=[
		'imp_broad_region_voyage_begin',
		'port_of_departure',
		'int_first_port_emb',
		'int_third_port_dis',
		'int_fourth_port_dis',
		'int_third_place_region_slave_landing',
		'int_fourth_place_region_slave_landing',
		'int_second_port_emb',
		'int_first_region_purchase_slaves',
		'int_second_region_purchase_slaves',
		'int_first_port_dis',
		'int_second_port_dis',
		'int_first_region_slave_landing',
		'imp_principal_region_slave_dis',
		'int_second_place_region_slave_landing',
		'first_place_slave_purchase',
		'second_place_slave_purchase',
		'third_place_slave_purchase',
		'first_region_slave_emb',
		'second_region_slave_emb',
		'third_region_slave_emb',
		'first_landing_place',
		'second_landing_place',
		'third_landing_place',
		'first_landing_region',
		'second_landing_region',
		'third_landing_region',
		'place_voyage_ended',
		'imp_port_voyage_begin',
		'principal_place_of_slave_purchase',
		'imp_principal_place_of_slave_purchase',
		'imp_principal_region_of_slave_purchase',
		'imp_broad_region_of_slave_purchase',
		'principal_port_of_slave_dis',
		'imp_principal_port_slave_dis',
		'imp_broad_region_slave_dis'
	]
	verbose_name_plural="Itinerary"
	exclude= [
		'port_of_call_before_atl_crossing',
		'number_of_ports_of_call',
		'region_of_return',
		'broad_region_of_return',
		'imp_region_voyage_begin',
		'imp_broad_region_voyage_begin'
		
	]
	classes = ['collapse']
	can_delete=False

class VoyageOutcomeInline(nested_admin.NestedStackedInline):
	model=VoyageOutcome
	extra=0
	classes = ['collapse']
	can_delete=False

class SourceVoyageConnectionInline(nested_admin.NestedStackedInline):
	ordering=['id']
	model=SourceVoyageConnection
	autocomplete_fields=['source']
	extra=0
	classes=['collapse']


class EnslavedInRelationInline_b(nested_admin.NestedStackedInline):
	model=EnslavedInRelation
	autocomplete_fields=['enslaved']
# 	readonly_fields=['relation']
# 	classes = ['collapse']
# 	sortable_field_name='id'
	extra=0


class EnslaverInRelationInline_b(nested_admin.NestedStackedInline):
	model=EnslaverInRelation
	autocomplete_fields=[
		'enslaver_alias'
	]
	verbose_name_plural = "Enslavers"
	extra=0


class EnslavementRelationInline(nested_admin.NestedStackedInline):
	model = EnslavementRelation
	inlines=[
		EnslavedInRelationInline_b,
		EnslaverInRelationInline_b
	]
	classes = ['collapse']
	extra=0
	exclude=['source','place','text_ref','unnamed_enslaved_count','date','amount','is_from_voyages']


class CargoTypeAdmin(admin.ModelAdmin):
	search_fields=['name']
	list_fields=['name']

class CargoConnectionInline(nested_admin.NestedStackedInline):
	model=VoyageCargoConnection
	autocomplete_fields=['cargo']
	classes = ['collapse']
	extra=0


# class AfricanInfoInline(nested_admin.NestedStackedInline):
# 	model = Voyage.african_info.through
# 	classes = ['collapse']
# 	extra=0

class VoyageAdmin(nested_admin.NestedModelAdmin):
	inlines=(
		VoyageDatesInline,
		VoyageItineraryInline,
		SourceVoyageConnectionInline,
		EnslavementRelationInline,
		VoyageCrewInline,
		VoyageOutcomeInline,
		VoyageShipInline,
		VoyageSlavesNumbersInline,
# 		AfricanInfoInline,
		CargoConnectionInline
	)
	exclude=['african_info_voyages']
	fields=['voyage_id','dataset','voyage_in_cd_rom']
	list_display=('voyage_id','get_ship','get_yearam')
	search_fields=('voyage_id','voyage_ship__ship_name')
	
admin.site.register(Voyage, VoyageAdmin)
admin.site.register(VoyageSparseDate,VoyageSparseDateAdmin)
admin.site.register(ParticularOutcome, ParticularOutcomeAdmin)
admin.site.register(SlavesOutcome, SlavesOutcomeAdmin)
admin.site.register(VesselCapturedOutcome, VesselCapturedOutcomeAdmin)
admin.site.register(OwnerOutcome, OwnerOutcomeAdmin)
admin.site.register(Resistance, ResistanceAdmin)
admin.site.register(Nationality)
admin.site.register(CargoType,CargoTypeAdmin)
admin.site.register(CargoUnit)
# admin.site.register(AfricanInfo)

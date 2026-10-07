from django.contrib import admin
from django import forms
from geo.models import *

#this looks semantically backwards to me.... but the data is being stored properly
class ChildOfInLine(admin.TabularInline):
	model=Location
	verbose_name = "Child"
# 	readonly_fields=['latitude','longitude','name','location_type','value','spatial_extent']
	verbose_name_plural="Children"
	can_delete=False
	classes=["collapse"]
	extra=0


class LocationAdmin(admin.ModelAdmin):
	inlines=(
		ChildOfInLine,
	)
	fields=[
		'name',
		'value',
		'location_type',
		'longitude',
		'latitude',
		'parent'
	]
	list_display=('name','value','longitude','latitude','location_type')
	search_fields=('name','value')
# 	readonly_fields=['value','name','parent','children','location_type']
	model=Location

admin.site.register(Location,LocationAdmin)


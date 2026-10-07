from django.contrib import admin
from document.models import *
from past.models import *
import nested_admin
from voyage.models import *


class TranscriptionInline(nested_admin.NestedStackedInline):
	model=Transcription
	max_num=1
	classes = ['collapse']
	verbose_name_plural="Transcriptions"
	can_delete=False

class PageAdmin(nested_admin.NestedModelAdmin):
	readonly_fields=['page_url','image_filename','iiif_baseimage_url']
	search_fields=['page_url','image_filename']
	list_display=['page_url','image_filename']
	inlines=[
		TranscriptionInline,
	]
	model=Page

class ShortRefAdmin(admin.ModelAdmin):
	model=ShortRef
	search_fields=('name','transkribus_docId')
	list_display=('name','transkribus_docId')

class SourceEnslavedConnectionInline(admin.StackedInline):
	model=SourceEnslavedConnection
	autocomplete_fields=['enslaved']
	exclude_fields=['source']
	extra=0
	classes=['collapse']
	verbose_name_plural="Enslaved People"

class SourceEnslaverConnectionInline(admin.StackedInline):
	model=SourceEnslaverConnection
	autocomplete_fields=['enslaver']
	exclude_fields=['source']
	extra=0
	classes=['collapse']
	verbose_name_plural="Enslavers"
	
class SourceVoyageConnectionInline(admin.StackedInline):
	model=SourceVoyageConnection
	autocomplete_fields=['voyage']
	exclude_fields=['source']
	extra=0
	classes=['collapse']
	verbose_name_plural="Voyages"

class DocSparseDateAdmin(admin.ModelAdmin):
	model=DocSparseDate
	search_fields=['m','d','y']

class SourceEnslavementRelationConnectionInline(admin.StackedInline):
	model=SourceEnslavementRelationConnection
	autocomplete_fields=['enslavement_relation']
	extra=0
	search_fields=['id']
	classes=['collapse']
	verbose_name_plural="Enslavement Relations"


class SourceAdmin(admin.ModelAdmin):
	model=Source
	inlines=[
		SourceEnslavedConnectionInline,
		SourceEnslaverConnectionInline,
		SourceVoyageConnectionInline,
		SourceEnslavementRelationConnectionInline
	]
	search_fields=['title','zotero_item_id','short_ref__name']
	autocomplete_fields=['short_ref','date']
# 	readonly_fields=['item_url','zotero_item_id','zotero_group_id']
	list_display=('title','short_ref','zotero_item_id','human_reviewed')

admin.site.register(Source, SourceAdmin)
admin.site.register(ShortRef,ShortRefAdmin)
admin.site.register(DocSparseDate,DocSparseDateAdmin)
admin.site.register(Page,PageAdmin)
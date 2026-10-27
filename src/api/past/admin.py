from django.contrib import admin
from past.models import *
from document.models import *
import nested_admin

class EnslavedInRelationInline(nested_admin.NestedStackedInline):
	model=EnslavedInRelation
	readonly_fields=['relation']
	classes = ['collapse']
	verbose_name_plural="Enslavement Relations"
	extra=0

class EnslaverInRelationInline(nested_admin.NestedStackedInline):
	model=EnslaverInRelation
	autocomplete_fields=[
		'enslaver_alias'
	]
	readonly_fields=['relation']
	classes = ['collapse']
	extra=0

class EnslaverAliasAdmin(nested_admin.NestedModelAdmin):
	autocomplete_fields=['identity']
	search_fields=['alias']
	readonly_fields=['manual_id','legacy_id']



class EnslavedInRelationInline_c(nested_admin.NestedStackedInline):
	model=EnslavedInRelation
	autocomplete_fields=['enslaved']
# 	readonly_fields=['relation']
	classes = ['collapse']
# 	sortable_field_name='id'
	extra=0
	verbose_name_plural='Enslaved People'


class EnslaverInRelationInline_c(nested_admin.NestedStackedInline):
	model=EnslaverInRelation
	autocomplete_fields=[
		'enslaver_alias'
	]
	verbose_name_plural = "Enslavers"
	classes = ['collapse']
	extra=0

class EnslavementRelationInline(nested_admin.NestedStackedInline):
	model = EnslavementRelation
	autocomplete_fields=['place']
	classes = ['collapse']
	extra=0
	exclude=['source','text_ref','date','amount','is_from_voyages']

class EnslavementRelationAdmin(nested_admin.NestedModelAdmin):
	model=EnslavementRelation
	autocomplete_fields=['place','voyage']
	search_fields=['id','place','voyage']
	inlines=[EnslaverInRelationInline_c,EnslavedInRelationInline_c]


class EnslaverInRelationInline(nested_admin.NestedStackedInline):
	model=EnslaverInRelation
	verbose_name_plural="Enslaver Alias-to-EnslavementRelation"
	extra=0
	classes=['collapse']

class EnslaverAliasInline(nested_admin.NestedStackedInline):
	model=EnslaverAlias
	classes=['collapse']
	readonly_fields=['manual_id','legacy_id']
	
	extra=0
	
class EnslaverSourceConnectionInline(nested_admin.NestedStackedInline):
	model=SourceEnslaverConnection
	autocomplete_fields=['source']
	extra=0
	classes=['collapse']
	verbose_name_plural="Bibliographic sources"

class EnslaverIdentityAdmin(nested_admin.NestedModelAdmin):
	inlines=(
		EnslaverAliasInline,
		EnslaverSourceConnectionInline
	)
	autocomplete_fields=['birth_place','death_place','principal_location']
	search_fields=['principal_alias',]

class EnslavedSourceConnectionInline(nested_admin.NestedStackedInline):
	model=SourceEnslavedConnection
	autocomplete_fields=['source']
	extra=0
	classes=['collapse']
	verbose_name_plural="Bibliographic sources"

class EnslavedAdmin(nested_admin.NestedModelAdmin):
	autocomplete_fields=[
		'post_disembark_location'
	]
	inlines=[EnslavedSourceConnectionInline,EnslavedInRelationInline]
	search_fields=['documented_name']

admin.site.register(EnslavementRelation,EnslavementRelationAdmin)
admin.site.register(EnslaverIdentity,EnslaverIdentityAdmin)
admin.site.register(EnslaverAlias,EnslaverAliasAdmin)
admin.site.register(Enslaved,EnslavedAdmin)
admin.site.register(EnslaverRole)
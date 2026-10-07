from __future__ import absolute_import, unicode_literals

import operator
import threading
from typing import Iterable
from builtins import range, str
from functools import reduce
from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.db import (connection, models, transaction)
from django.db.models import (Aggregate, Case, CharField, Count, F, Func, IntegerField, Max, Min, Q, Sum, Value, When)
from django.db.models.expressions import Subquery, OuterRef
from django.db.models.fields import TextField
from django.db.models.functions import Coalesce, Concat, Length, Substr
from django.db.models.sql import RawQuery
import re
import uuid
from common.models import NamedModelAbstractBase,SparseDateAbstractBase
from voyage.models import Voyage,VoyageShip,VoyageSparseDate,VoyageItinerary
from geo.models import Location

class PASTSparseDate(SparseDateAbstractBase):
	pass

class EnslaverInfoAbstractBase(models.Model):
	principal_alias = models.CharField(db_index=True,max_length=255)
	#cached nested field for searching
	voyages=models.ManyToManyField(Voyage,db_index=True)
	roles=models.ManyToManyField('EnslaverRole',db_index=True)
	# Personal info.
	birth_year = models.IntegerField(null=True,blank=True)
	birth_month = models.IntegerField(null=True,blank=True)
	birth_day = models.IntegerField(null=True,blank=True)
	birth_place = models.ForeignKey(
		Location,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='+'
	)
	death_year = models.IntegerField(null=True,blank=True)
	death_month = models.IntegerField(null=True,blank=True)
	death_day = models.IntegerField(null=True,blank=True)
	death_place = models.ForeignKey(
		Location,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='+'
	)
	father_name = models.CharField(db_index=True,max_length=255, null=True,blank=True)
	father_occupation = models.CharField(db_index=True,max_length=255, null=True,blank=True)
	mother_name = models.CharField(db_index=True,max_length=255, null=True,blank=True)
	probate_date = models.CharField(db_index=True,max_length=12, null=True,blank=True)
	will_value_pounds = models.CharField(db_index=True,max_length=12, null=True,blank=True)
	will_value_dollars = models.CharField(db_index=True,max_length=12, null=True,blank=True)
	will_court = models.CharField(db_index=True,max_length=12, null=True,blank=True)
	principal_location = models.ForeignKey(
		Location,
		null=True,
		on_delete=models.SET_NULL,
		db_index=True,
		blank=True,
		related_name='+'
	)
	notes = models.CharField(null=True, max_length=8192,blank=True)
	is_natural_person = models.BooleanField(null=False, default=True,blank=True)
	last_updated=models.DateTimeField(auto_now=True)
	number_enslaved_people=models.IntegerField(null=True,blank=True)
	human_reviewed=models.BooleanField(default=False,blank=True,null=True)
	#It's going to be hairy mapping all this data over from legacy
	#so I'm going to have to maintain a sort of shadow pk for use in migrations
	legacy_id=models.IntegerField(null=True,blank=True)

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return "Enslaver info: " + self.principal_alias
	 
	class Meta:
		abstract = True
		ordering=['id']


class EnslaverIdentity(EnslaverInfoAbstractBase):

	class Meta:
		verbose_name = 'Enslaver Identity'
		verbose_name_plural = 'Enslaver Identities'
		ordering=['id']

class EnslaverAlias(models.Model):
	"""
	An alias represents a name appearing in a record that is mapped to
	a consolidated identity. The same individual may appear in multiple
	records under different names (aliases).
	"""
	identity = models.ForeignKey(EnslaverIdentity, on_delete=models.CASCADE, related_name='aliases')
	alias = models.CharField(db_index=True,max_length=255)
	
	# The manual id can be used to track the original entries in sheets produced
	# by the researchers.
	manual_id = models.CharField(db_index=True,max_length=30, null=True)
	last_updated=models.DateTimeField(auto_now=True)
	human_reviewed=models.BooleanField(default=False,blank=True,null=True)
	#It's going to be hairy mapping all this data over from legacy
	#so I'm going to have to maintain a sort of shadow pk for use in migrations
	legacy_id=models.IntegerField(null=True,blank=True)


	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return "EnslaverAlias: " + self.alias

	class Meta:
		verbose_name = 'Enslaver alias'
		verbose_name_plural = "Enslaver aliases"
		ordering=['id']

class EnslaverRole(NamedModelAbstractBase):
	pass

class LanguageGroup(NamedModelAbstractBase):
	
	uuid=models.UUIDField(default=uuid.uuid4, editable=False,null=True)
	
	longitude = models.FloatField("Longitude of point",
									null=True)
	latitude = models.FloatField("Latitude of point",
								   null=True)
	shape=models.JSONField(
		"Geojson Polygon",
		null=True,
		blank=True
	)

class ModernCountry(NamedModelAbstractBase):
	
	uuid=models.UUIDField(default=uuid.uuid4, editable=False,null=True)
	
	longitude = models.FloatField("Longitude of Country",
									null=False)
	latitude = models.FloatField("Latitude of Country",
								   null=False)
	languages = models.ManyToManyField(LanguageGroup)
	
	shape=models.JSONField(
		"Geojson Polygon",
		null=True,
		blank=True
	)
	
	class Meta:
		verbose_name = "Modern country"
		verbose_name_plural = "Modern countries"


class RegisterCountry(NamedModelAbstractBase):
	
	class Meta:
		verbose_name = "Register country"
		verbose_name_plural = "Register countries"


class AltLanguageGroupName(NamedModelAbstractBase):
	language_group = models.ForeignKey(
		LanguageGroup,
		null=False,
		related_name='alt_names',
		on_delete=models.CASCADE
	)

class CaptiveFate(NamedModelAbstractBase):
	pass


class CaptiveStatus(NamedModelAbstractBase):

	class Meta:
		verbose_name = "Captive status"
		verbose_name_plural = "Captive statuses"

class Gender(NamedModelAbstractBase):
	
	class Meta:
		verbose_name = "Gender"

class Enslaved(models.Model):
	"""
	Enslaved person.
	"""
	# For African Origins dataset documented_name is an African Name.
	# For Oceans of Kinfolk, this field is used to store the Western
	# Name of the enslaved.
	enslaved_id = models.IntegerField(db_index=True,unique=True,blank=False,null=False)
	documented_name = models.CharField(db_index=True,max_length=100, blank=True,null=True)
	name_first = models.CharField(db_index=True,max_length=100, null=True, blank=True)
	name_second = models.CharField(db_index=True,max_length=100, null=True, blank=True)
	name_third = models.CharField(db_index=True,max_length=100, null=True, blank=True)
	modern_name = models.CharField(db_index=True,max_length=100, null=True, blank=True)
	# Certainty is used for African Origins only.
	editor_modern_names_certainty = models.CharField(db_index=True,max_length=255,
													 null=True,
													 blank=True)
	# Personal data
	age = models.IntegerField(null=True, db_index=True,blank=True)
	gender_int = models.IntegerField(null=True, db_index=True,blank=True)
	gender = models.ForeignKey(Gender,on_delete=models.SET_NULL,blank=True,null=True)
	height = models.FloatField(null=True, verbose_name="Height in inches", db_index=True,blank=True)
	skin_color = models.CharField(max_length=100, null=True, db_index=True,blank=True)
	language_group = models.ForeignKey(
		LanguageGroup,
		on_delete=models.SET_NULL,
		db_index=True,null=True,blank=True
	)
	register_country = models.ForeignKey(
		RegisterCountry,
		null=True,
		on_delete=models.SET_NULL,
		db_index=True,blank=True
	)
	# For Kinfolk, this is the Last known location field.
	post_disembark_location = models.ForeignKey(
		Location, null=True,
		on_delete=models.SET_NULL,
		db_index=True,
		related_name='+',blank=True
	)
	last_known_date = models.OneToOneField(
		PASTSparseDate,
		verbose_name="Last known date",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="+"
	)
	captive_fate = models.ForeignKey(CaptiveFate, null=True, on_delete=models.SET_NULL, db_index=True,blank=True)
	captive_status = models.ForeignKey(CaptiveStatus, null=True, on_delete=models.SET_NULL, db_index=True,blank=True)
	dataset = models.IntegerField(null=True, default=0, db_index=True,blank=True)
	notes = models.CharField(null=True, max_length=8192,blank=True)
	last_updated=models.DateTimeField(auto_now=True)
	human_reviewed=models.BooleanField(default=False,blank=True,null=True)

	def __str__(self):
		if self.documented_name is None:
			return ''
		else:
			return self.documented_name
			
	class Meta:
		verbose_name_plural = "Enslaved People"
		ordering=['id']

class EnslavedName(models.Model):
	name = models.CharField(db_index=True,max_length=255, null=False, blank=False)
	language = models.CharField(db_index=True,max_length=3, null=False, blank=False)
	recordings_count = models.IntegerField()

class EnslavementRelationType(NamedModelAbstractBase):
	pass

class EnslavementRelation(models.Model):
	"""
	Represents a relation involving any number of enslavers and enslaved
	individuals.
	"""
# 	id = models.IntegerField(primary_key=True)
	relation_type = models.ForeignKey(EnslavementRelationType, null=False,blank=False, on_delete=models.DO_NOTHING)
	place = models.ForeignKey(Location, null=True,blank=True, on_delete=models.SET_NULL, related_name='+')
	date = models.CharField(db_index=True,max_length=12, null=True,blank=True,
		help_text="Date in MM,DD,YYYY format with optional fields.")
	amount = models.FloatField(null=True,blank=True)
	voyage = models.ForeignKey(
		Voyage,
		related_name="voyage_enslavement_relations",
		null=True,blank=True,
		on_delete=models.SET_NULL
	)
	is_from_voyages=models.BooleanField(default=False,null=True,blank=True)

class EnslavementRelationDate(SparseDateAbstractBase):
	enslavement_relation=models.OneToOneField(EnslavementRelation,on_delete=models.CASCADE)
	pass

class EnslavedInRelation(models.Model):
	"""
	Associates an enslaved in a slave relation.
	"""

# 	id = models.IntegerField(primary_key=True)
	relation = models.ForeignKey(
		EnslavementRelation,
		related_name="enslaved_in_relation",
		null=False,
		on_delete=models.CASCADE)
	enslaved = models.ForeignKey(Enslaved,
		related_name="enslaved_relations",
		null=False,
		on_delete=models.CASCADE)
# 	class Meta:
# 		unique_together = ('relation', 'enslaved')
	class Meta:
		ordering=['id']

class EnslaverInRelation(models.Model):
	"""
	Associates an enslaver in a slave relation.
	"""

# 	id = models.IntegerField(primary_key=True)
	relation = models.ForeignKey(
		EnslavementRelation,
		related_name="relation_enslavers",
		null=False,
		on_delete=models.CASCADE,
		db_index=True)
	enslaver_alias = models.ForeignKey(
		EnslaverAlias,
		related_name="enslaver_relations",
		null=False,
		on_delete=models.CASCADE
	)
	
	roles = models.ManyToManyField(
		EnslaverRole,
		help_text="The role(s) of the enslaver in this relation",
		db_index=True
	)
	class Meta:
# 		unique_together = ('relation', 'enslaver_alias','role')
		ordering=['id']



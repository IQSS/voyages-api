from __future__ import unicode_literals

import threading
from builtins import str
from itertools import groupby

from django.db import models


class ExportArea(models.Model):
	"""
	Class represents Export area entity.
	"""

	name = models.CharField(max_length=200, verbose_name="Export area name")
	order_num = models.IntegerField()
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	show_at_zoom = models.IntegerField()
	show_on_map = models.BooleanField()

	def __lt__(self, other):
		return (self.name, self.order_num) < (other.name, other.order_num)

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return self.name


class ExportRegion(models.Model):
	"""
	Class represents Export region entity.
	"""

	name = models.CharField(max_length=200, verbose_name="Export region name")
	order_num = models.IntegerField()
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	show_at_zoom = models.IntegerField()
	show_on_map = models.BooleanField()
	export_area = models.ForeignKey(ExportArea, on_delete=models.CASCADE)

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return self.name


class ImportArea(models.Model):
	"""
	Class represents Import area entity.
	"""

	name = models.CharField(max_length=200, verbose_name="Import area name")
	order_num = models.IntegerField()
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	show_at_zoom = models.IntegerField()
	show_on_map = models.BooleanField()

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return self.name

	def __lt__(self, other):
		return (self.name, self.order_num) < (other.name, other.order_num)


class ImportRegion(models.Model):
	"""
	Class represents Import region entity.
	"""

	name = models.CharField(max_length=200, verbose_name="Import region name")
	order_num = models.IntegerField()
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	show_at_zoom = models.IntegerField()
	show_on_map = models.BooleanField()
	import_area = models.ForeignKey(ImportArea, on_delete=models.CASCADE)

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return self.name


class Nation(models.Model):
	name = models.CharField(max_length=200, null=True, blank=True)
	order_num = models.IntegerField()

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return self.name


class Estimate(models.Model):
	"""
	Class represents Estimate entity
	"""

	nation = models.ForeignKey(Nation, on_delete=models.CASCADE)
	year = models.IntegerField()
	embarkation_region = models.ForeignKey(
		ExportRegion, null=True, blank=True, on_delete=models.CASCADE)
	disembarkation_region = models.ForeignKey(
		ImportRegion, null=True, blank=True, on_delete=models.CASCADE)
	embarked_slaves = models.IntegerField(null=True, blank=True)
	disembarked_slaves = models.IntegerField(null=True, blank=True)

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return str(self.id)

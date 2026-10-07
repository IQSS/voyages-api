from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

# Create your models here.

def year_mod(the_year, mod, start):
	if the_year is None:
		return None
	return 1 + ((the_year - start - 1) // mod)


class NamedModelAbstractBase(models.Model):
	
	name = models.CharField(max_length=255,unique=True)

	def __str__(self):
		return self.__unicode__()

	def __unicode__(self):
		return str(self.id) + ", " + self.name

	class Meta:
		abstract = True

class SparseDateAbstractBase(models.Model):
	day = models.IntegerField(
		null=True,
		blank=True,
		validators=[MinValueValidator(1),MaxValueValidator(31)],
		db_index=True
	)
	month = models.IntegerField(
		null=True,
		blank=True,
		validators=[MinValueValidator(1),MaxValueValidator(12)],
		db_index=True
	)
	year = models.IntegerField(
		null=True,
		blank=True,
		validators=[MinValueValidator(0),MaxValueValidator(2050)],
		db_index=True
	)

	def __str__(self):
		m=self.month
		d=self.day
		y=self.year
		mdy=[m,d,y]
		monthindex=[
			"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"
		]
		if None not in mdy:
			return ",".join([str(i) for i in mdy])
		elif m is not None:
			if y is not None:
				return f"{monthindex[m-1]} {y}"
			else:
				return monthindex[m-1]
		elif y is not None:
			return str(y)
		
	class Meta:
		abstract = True
		ordering=['year','month','day']

# Create your models here.
class SavedQuery(models.Model):
	"""
	Used to store a query for later use in a permanent link.
	"""

	ID_LENGTH = 8

	# This is the short sequence of characters that will be used when repeating
	# the query.
	id = models.CharField(max_length=8, primary_key=True)
	# A hash string so that the query can be quickly located.
	hash_id = models.CharField(
		max_length=255,
		unique=True,
		default=''
	)
	# The actual query string.
	query = models.JSONField()
	# Indicates whether this is a legacy query or a new JSON format query
	
	front_end_path=models.CharField(max_length=100,blank=True,null=True)
	
	endpoint=models.CharField(
		choices=[
			('assessment','assessment'),
			('past/enslaved','past/enslaved'),
			('past/enslaver','past/enslaver'),
			('voyage','voyage')
		],
		max_length=50,
		default='voyage'
	)
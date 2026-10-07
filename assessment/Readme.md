This is the oldest part of the voyages site. It is also the most-visited!

Easy-peasy migration:

	insert into assessment_exportarea select * from voyages_prod.assessment_exportarea;
	insert into assessment_exportregion select * from voyages_prod.assessment_exportregion;
	insert into assessment_importarea select * from voyages_prod.assessment_importarea;
	insert into assessment_importregion select * from voyages_prod.assessment_importregion;
	insert into assessment_nation select * from voyages_prod.assessment_nation;
	insert into assessment_estimate select * from voyages_prod.assessment_estimate;
	
Ta-da.
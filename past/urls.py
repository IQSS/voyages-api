from django.urls import path

from . import views

urlpatterns = [
	path('enslaved/', views.EnslavedList.as_view()),
	path('enslaved/<int:enslaved_id>',views.EnslavedGET.as_view()),
	path('enslaved/aggregations/',views.EnslavedAggregations.as_view()),
	path('enslaved/dataframes/',views.EnslavedDataFrames.as_view()),
	path('enslaved/aggroutes/',views.EnslavedAggRoutes.as_view()),
	path('enslavementrelation/dataframes/',views.EnslavementRelationDataFrames.as_view()),
	path('enslaver/',views.EnslaverList.as_view()),
	path('enslaver/<int:id>',views.EnslaverGET.as_view()),
	path('enslaver/aggregations/',views.EnslaverAggregations.as_view()),
	path('enslaver/dataframes/',views.EnslaverDataFrames.as_view()),
	path('networks/',views.PASTNetworks.as_view()),
	path('enslaved/geotree/',views.EnslavedGeoTreeFilter.as_view()),
	path('enslaver/geotree/',views.EnslaverGeoTreeFilter.as_view()),
	path('enslaved/languagegrouptree/',views.EnslavedLanguageGroupTree.as_view()),
	path('enslaver/EnslaverRoleList/',views.EnslaverRoleList.as_view()),
	path('GenderList/',views.GenderList.as_view()),
	path('CaptiveFateList/',views.CaptiveFateList.as_view()),
	path('EnslavedVoyageOutcome/',views.EnslavedVoyageOutcome.as_view()),
	path('IndexEnslaverData/',views.IndexEnslaverData)
]

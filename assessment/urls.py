from django.urls import path

from . import views

urlpatterns = [
	path('<int:id>', views.AssessmentList.as_view()),
	path('dataframes/',views.EstimateDataFrames.as_view()),
	path('crosstabs/',views.EstimateCrossTabs.as_view()),
	path('timelines/',views.EstimateTimeline.as_view()),
	path('aggroutes/',views.EstimateAggRoutes.as_view())
	
	
]
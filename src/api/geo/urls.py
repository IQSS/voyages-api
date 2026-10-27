from django.urls import path

from . import views

urlpatterns = [
	path('geotree/',views.GeoTree.as_view()),
    path('<int:value>',views.LocationRETRIEVE.as_view())
]
    
    
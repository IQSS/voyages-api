from django.urls import path


from . import views

urlpatterns = [
	path('global/', views.GlobalSearch.as_view()),
	path('schemas/', views.Schemas.as_view()),
	path('usesavedsearch/<str:id>', views.UseSavedSearch.as_view()),
	path('makesavedsearch/', views.MakeSavedSearch.as_view()),
	path('RedisFlush/',views.RedisFlush)
]
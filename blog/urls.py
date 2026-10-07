from django.urls import path
from . import views

urlpatterns = [
    path('', views.PostList.as_view()),
    path('autocomplete/', views.PostTextFieldAutoComplete.as_view()),
    path('author/', views.AuthorList.as_view()),
    path('institution/', views.InstitutionList.as_view())
]
    
    
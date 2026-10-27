from django.urls import path

from . import views

urlpatterns = [
    path('records/', views.VoyageAnimation.as_view()),
    path('get-compiled-routes/', views.VoyageAnimationGetCompiledRoutes.as_view()),
    path('nations/', views.VoyageAnimationGetNations.as_view())
    
]

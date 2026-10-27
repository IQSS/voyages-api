from django.urls import path,include
from . import views

urlpatterns = [
	#MAIN ENDPOINT FOR POST REQUESTS (BUILT FOR VOYAGES-FRONTEND)
	path('',views.SourceList.as_view()),
# 	path('autocomplete/',views.SourceCharFieldAutoComplete.as_view()),
	#CRUD ENDPOINTS (FOR CONTRIBUTE CLIENTS)
# 	path('CREATE/',views.SourceCreate.as_view()),
# 	path('DESTROY/<int:id>',views.SourceDestroy.as_view()),
# 	path('UPDATE/<int:id>',views.SourceUpdate.as_view()),
# 	path('RETRIEVE/<int:id>',views.SourceRetrieve.as_view()),
	#READ-ONLY CONTROLLED VOCAB ENDPOINTS (FOR CONTRIBUTE CLIENTS)
	path('SourceTypeList/',views.SourceTypeList.as_view()),
	path('DocumentSearch/',views.DocumentSearch.as_view()),
	path('SourceList/',views.SourceList.as_view())
]



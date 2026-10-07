from django.urls import path,include
from . import views

urlpatterns = [
	#MAIN ENDPOINT FOR POST REQUESTS (BUILT FOR VOYAGES-FRONTEND)
	path('',views.SourceList.as_view()),
	#GALLERY VIEW -- LET'S KILL THIS ASAP
	path('gallery',views.Gallery),
	path('gallery/<int:collection_id>',views.Gallery,name="gallery"),
	path('gallery/<int:collection_id>/<int:pagenumber>',views.Gallery,name="gallery"), 
# 	path('autocomplete/',views.SourceCharFieldAutoComplete.as_view()),
	path('gallery/single/',views.source_page,name="source_page"),
	path('gallery/single/<int:source_id>',views.source_page,name="source_page"),
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



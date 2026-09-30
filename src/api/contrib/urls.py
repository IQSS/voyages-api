from django.urls import path
from .views import batch_data_api, location_tree, publish_batch, publication_status

urlpatterns = [
    path('data', batch_data_api, name='contrib_data_api'),
    path('location_tree', location_tree, name='location_tree'),
    path('publish_batch', publish_batch, name='publish_batch'),
    # Updated to capture publication_key from the URL: /publication_status/<key>
    path('publication_status/<str:publication_key>', publication_status, name='publication_status'),
]

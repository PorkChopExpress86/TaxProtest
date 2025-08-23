from django.urls import path
from . import views

app_name = "comparables"

urlpatterns = [
    path("", views.search, name="search"),
    path("export/<str:fmt>/", views.export_search_results, name="export_search_results"),
    path("comparables/<str:acct>/", views.comparables_view, name="comparables"),
    path("comparables/<str:acct>/export/<str:fmt>/", views.export_comparables, name="export_comparables"),
]

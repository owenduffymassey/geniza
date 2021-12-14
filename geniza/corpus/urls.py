from django.urls import path

from geniza.corpus import views as corpus_views

app_name = "corpus"

urlpatterns = [
    path(
        "documents/", corpus_views.DocumentSearchView.as_view(), name="document-search"
    ),
    path(
        "documents/<int:pk>/",
        corpus_views.DocumentDetailView.as_view(),
        name="document",
    ),
    path(
        "documents/<int:pk>/scholarship/",
        corpus_views.DocumentScholarshipView.as_view(),
        name="document-scholarship",
    ),
    path(
        "documents/<int:pk>/iiif/manifest/",
        corpus_views.DocumentManifest.as_view(),
        name="document-manifest",
    ),
    path(
        "documents/<int:pk>/iiif/annotations/",
        corpus_views.DocumentAnnotationList.as_view(),
        name="document-annotations",
    ),
    path(
        "documents/<int:pk>/iiif/canvas/1",
        corpus_views.DocumentCanvas.as_view(),
        name="document-canvas",
    ),
    path("export/pgp-metadata-old/", corpus_views.pgp_metadata_for_old_site),
]

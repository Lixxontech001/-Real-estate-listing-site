from django.urls import path

from .views import ListingDocumentView, UserDocumentView

urlpatterns = [
    # Access is enforced in the view's get_queryset(): realtor or staff only.
    path("<int:pk>/docs/", ListingDocumentView.as_view(), name="documents"),
    # Scoped to listings where the user has can_access_documents=True.
    path("profile/", UserDocumentView.as_view(), name="user-docs"),
]

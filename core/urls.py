from django.urls import path

from .views import AboutView, ImpressumView, IndexView, PrivacyView

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("about-us", AboutView.as_view(), name="about"),
    path("impressum", ImpressumView.as_view(), name="impressum"),
    path("privacy", PrivacyView.as_view(), name="privacy"),
]

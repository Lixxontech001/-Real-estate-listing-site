from django.urls import path

from .views import (
    ProfileUpdateView,
    address,
    dashboard,
    login,
    logout,
    password_reset_request,
    register,
)

urlpatterns = [
    path("login", login, name="login"),
    path("register", register, name="register"),
    path("logout", logout, name="logout"),
    path("dashboard", dashboard, name="dashboard"),
    # No <int:pk>: the view is scoped to request.user. See ProfileUpdateView.
    path("profile", ProfileUpdateView.as_view(), name="profile"),
    path("profile/address", address, name="user-address"),
    path("password-reset", password_reset_request, name="password-reset"),
]

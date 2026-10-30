from django.urls import path

from accounts.views import public_profile
from reading.views import quote_feed

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("quotes/", quote_feed, name="quote_feed"),
    path("u/<str:username>/", public_profile, name="profile"),
]

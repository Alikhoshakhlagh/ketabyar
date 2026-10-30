from django.urls import path

from . import views

app_name = "reading"

urlpatterns = [
    path("shelf/", views.shelf, name="shelf"),
    path("books/<int:pk>/status/", views.set_status, name="set_status"),
    path("books/<int:pk>/progress/", views.update_progress, name="update_progress"),
    path("books/<int:pk>/rate/", views.rate_book, name="rate"),
    path("books/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("books/<int:pk>/review/", views.review_edit, name="review_edit"),
    path("reviews/<int:pk>/delete/", views.review_delete, name="review_delete"),
    path("reviews/<int:pk>/like/", views.review_like, name="review_like"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/new/", views.session_form, name="session_create"),
    path("sessions/<int:pk>/edit/", views.session_form, name="session_edit"),
    path("sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    path("quotes/", views.quote_list, name="quote_list"),
    path("quotes/new/", views.quote_form, name="quote_create"),
    path("quotes/<int:pk>/edit/", views.quote_form, name="quote_edit"),
    path("quotes/<int:pk>/delete/", views.quote_delete, name="quote_delete"),
    path("stats/", views.my_stats, name="stats"),
]

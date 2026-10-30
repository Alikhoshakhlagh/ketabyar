from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("books/", views.book_list, name="book_list"),
    path("books/new/", views.BookCreate.as_view(), name="book_create"),
    path("books/<int:pk>/edit/", views.BookUpdate.as_view(), name="book_edit"),
    path("books/<int:pk>/delete/", views.BookDelete.as_view(), name="book_delete"),
    path("authors/", views.author_list, name="author_list"),
    path("authors/new/", views.AuthorCreate.as_view(), name="author_create"),
    path("authors/<int:pk>/edit/", views.AuthorUpdate.as_view(), name="author_edit"),
    path("authors/<int:pk>/delete/", views.AuthorDelete.as_view(), name="author_delete"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/new/", views.CategoryCreate.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.CategoryUpdate.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", views.CategoryDelete.as_view(), name="category_delete"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/toggle/", views.user_toggle, name="user_toggle"),
    path("reviews/", views.review_list, name="review_list"),
    path("reviews/<int:pk>/moderate/", views.review_moderate, name="review_moderate"),
    path("activity/", views.activity_list, name="activity_list"),
    path("reports/", views.reports, name="reports"),
    path("reports/export.csv", views.reports_export, name="reports_export"),
]

from django.contrib import admin

from .models import Author, Book, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "color"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "birth_year"]
    search_fields = ["name"]


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "category", "publish_year", "pages", "created_at"]
    list_filter = ["category"]
    search_fields = ["title", "author__name", "translator", "isbn"]
    autocomplete_fields = ["author"]
    readonly_fields = ["created_by", "created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

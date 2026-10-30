from django.contrib import admin

from .models import Activity, Favorite, Quote, Rating, ReadingSession, Review, ReviewLike, ShelfEntry


@admin.register(ShelfEntry)
class ShelfEntryAdmin(admin.ModelAdmin):
    list_display = ["user", "book", "status", "current_page", "started_on", "finished_on"]
    list_filter = ["status"]
    search_fields = ["user__username", "book__title"]
    autocomplete_fields = ["user", "book"]


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["user", "book", "score", "updated_at"]
    list_filter = ["score"]
    search_fields = ["user__username", "book__title"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["book", "user", "title", "has_spoiler", "is_hidden", "created_at"]
    list_filter = ["is_hidden", "has_spoiler"]
    list_editable = ["is_hidden"]
    search_fields = ["title", "body", "book__title", "user__username"]


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ["short_text", "kind", "book", "user", "page", "is_public", "created_at"]
    list_filter = ["kind", "is_public"]
    search_fields = ["text", "book__title", "user__username"]

    @admin.display(description="متن")
    def short_text(self, obj):
        return obj.text[:60]


@admin.register(ReadingSession)
class ReadingSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "book", "date", "minutes", "pages_read"]
    list_filter = ["date"]
    date_hierarchy = "date"
    search_fields = ["user__username", "book__title"]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "verb", "book", "detail"]
    list_filter = ["verb"]
    search_fields = ["user__username", "book__title"]


admin.site.register(Favorite)
admin.site.register(ReviewLike)

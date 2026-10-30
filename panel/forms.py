from django import forms

from catalog.models import Author, Book, Category


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["title", "subtitle", "author", "translator", "category", "publisher", "publish_year", "pages",
                  "isbn", "description", "cover"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ["name", "country", "birth_year", "bio"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "color", "description"]
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {"slug": "مثلاً: roman یا رمان (بدون فاصله)"}

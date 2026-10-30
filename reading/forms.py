import datetime

from django import forms

from catalog.models import Book
from core.forms import JalaliDateField

from .models import Quote, ReadingSession, Review


class BookChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.title} — {obj.author.name}"


def _book_field():
    return BookChoiceField(label="کتاب", queryset=Book.objects.select_related("author").order_by("title"),
                           empty_label="یک کتاب انتخاب کنید")


class SessionForm(forms.ModelForm):
    book = _book_field()
    date = JalaliDateField(label="تاریخ", initial=datetime.date.today)

    class Meta:
        model = ReadingSession
        fields = ["book", "date", "minutes", "start_page", "end_page", "pages_read", "note"]
        widgets = {
            "minutes": forms.NumberInput(attrs={"min": 1, "max": 1440, "placeholder": "مثلاً ۴۵"}),
            "start_page": forms.NumberInput(attrs={"min": 0}),
            "end_page": forms.NumberInput(attrs={"min": 0}),
            "pages_read": forms.NumberInput(attrs={"min": 0}),
            "note": forms.TextInput(attrs={"placeholder": "مثلاً: فصل سوم را تمام کردم"}),
        }
        help_texts = {
            "pages_read": "اگر «از صفحه» و «تا صفحه» را پر کنید، خودکار حساب می‌شود.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pages_read"].required = False

    def clean_pages_read(self):
        return self.cleaned_data.get("pages_read") or 0

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date and date > datetime.date.today():
            raise forms.ValidationError("تاریخ جلسه نمی‌تواند در آینده باشد.")
        return date

    def clean(self):
        data = super().clean()
        book, start, end = data.get("book"), data.get("start_page"), data.get("end_page")
        if start is not None and end is not None and end < start:
            self.add_error("end_page", "صفحه‌ی پایان باید بعد از صفحه‌ی شروع باشد.")
        if book and book.pages and end and end > book.pages:
            self.add_error("end_page", f"این کتاب فقط {book.pages} صفحه دارد.")
        if start is not None and end is not None and end >= start:
            data["pages_read"] = end - start
        return data


class QuoteForm(forms.ModelForm):
    book = _book_field()

    class Meta:
        model = Quote
        fields = ["book", "kind", "text", "page", "note", "is_public"]
        widgets = {
            "kind": forms.RadioSelect,
            "text": forms.Textarea(attrs={"rows": 4, "placeholder": "جمله یا بخشی که برایتان مهم بود…"}),
            "note": forms.Textarea(attrs={"rows": 2, "placeholder": "چرا این بخش برایتان مهم بود؟ (فقط خودتان می‌بینید)"}),
            "page": forms.NumberInput(attrs={"min": 1}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["title", "body", "has_spoiler"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "یک جمله که نظرتان را خلاصه کند"}),
            "body": forms.Textarea(attrs={"rows": 8, "placeholder": "نظرتان درباره‌ی کتاب، نقاط قوت و ضعف…"}),
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 20:
            raise forms.ValidationError("نقد باید دست‌کم ۲۰ کاراکتر باشد.")
        return body


class ProgressForm(forms.Form):
    current_page = forms.IntegerField(label="صفحه‌ی فعلی", min_value=0)

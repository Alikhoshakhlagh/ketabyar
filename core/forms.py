import datetime

from django import forms

from core.jalali import format_jalali, from_jalali, to_en_digits


class JalaliDateField(forms.CharField):
    """
    فیلد تاریخ شمسی: کاربر می‌نویسد ۱۴۰۵/۰۷/۲۷ و در دیتابیس date میلادی ذخیره می‌شود.
    ارقام فارسی/عربی/انگلیسی و جداکننده‌های / - . همه پذیرفته می‌شوند.
    """

    default_error_messages = {"invalid": "تاریخ را به شکل ۱۴۰۵/۰۷/۲۷ وارد کنید."}

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            forms.TextInput(attrs={"placeholder": "۱۴۰۵/۰۷/۲۷", "dir": "ltr", "inputmode": "numeric",
                                   "class": "date-input"}),
        )
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, datetime.date):
            return format_jalali(value, "short")
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return None
        text = to_en_digits(value).strip().replace("-", "/").replace(".", "/")
        parts = [p for p in text.split("/") if p]
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")
        jy, jm, jd = (int(p) for p in parts)
        if jy < 100:  # «۰۵/۷/۲۷» → ۱۴۰۵
            jy += 1400
        try:
            return from_jalali(jy, jm, jd)
        except (ValueError, OverflowError):
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label="نام", max_length=150)
    last_name = forms.CharField(label="نام خانوادگی", max_length=150, required=False)
    email = forms.EmailField(label="ایمیل", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        help_texts = {"username": "فقط حروف انگلیسی، عدد و @/./+/-/_ ؛ در آدرس پروفایل شما استفاده می‌شود."}

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("این ایمیل قبلاً ثبت شده است.")
        return email


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar", "bio", "yearly_goal", "daily_goal_minutes", "is_public"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 3, "placeholder": "چه کتاب‌هایی دوست دارید؟"})}

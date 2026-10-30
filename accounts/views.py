from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from reading import stats
from reading.models import Activity, Favorite, Quote, Review, ShelfEntry
from reading.services import log

from .forms import ProfileForm, RegisterForm, UserForm


def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log(user, Activity.Verb.JOINED)
        login(request, user)
        messages.success(request, f"{user.first_name} عزیز، به کتاب‌یار خوش آمدید! اولین کتابتان را به قفسه اضافه کنید.")
        return redirect("catalog:book_list")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile_edit(request):
    user_form = UserForm(request.POST or None, instance=request.user)
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user.profile)
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, "پروفایل شما به‌روز شد.")
        return redirect("accounts:profile_edit")
    return render(request, "accounts/profile_edit.html", {"user_form": user_form, "profile_form": profile_form})


def public_profile(request, username):
    """صفحه‌ی عمومی هر کاربر — برای اشتراک‌گذاری تجربه‌ی مطالعه"""
    owner = get_object_or_404(get_user_model().objects.select_related("profile"), username=username, is_active=True)
    is_me = request.user == owner
    can_see = owner.profile.is_public or is_me or request.user.is_staff
    context = {"owner": owner, "is_me": is_me, "can_see": can_see}
    if not can_see:
        return render(request, "accounts/public_profile.html", context)

    entries = owner.shelf_entries.select_related("book__author", "book__category")
    total_minutes = owner.sessions.aggregate(m=Sum("minutes"))["m"] or 0
    streak_now, streak_best = stats.streaks(owner.sessions.all())
    context.update({
        "reading": entries.filter(status=ShelfEntry.Status.READING),
        "read": entries.filter(status=ShelfEntry.Status.READ).order_by("-finished_on")[:12],
        "read_count": entries.filter(status=ShelfEntry.Status.READ).count(),
        "to_read_count": entries.filter(status=ShelfEntry.Status.TO_READ).count(),
        "favorites": [f.book for f in Favorite.objects.filter(user=owner).select_related("book__author", "book__category")[:8]],
        "reviews": Review.objects.filter(user=owner, is_hidden=False).select_related("book__author", "book__category")[:5],
        "quotes": Quote.objects.filter(user=owner, is_public=True).select_related("book__author")[:6],
        "total_minutes": total_minutes,
        "streak_now": streak_now, "streak_best": streak_best,
        "goal": stats.yearly_goal(owner),
        "share_url": request.build_absolute_uri(),
    })
    return render(request, "accounts/public_profile.html", context)

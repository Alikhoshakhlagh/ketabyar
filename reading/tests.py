"""
تست‌های خودکار:  python manage.py test
"""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from catalog.models import Author, Book, Category
from core.forms import JalaliDateField
from core.jalali import from_jalali, to_jalali

from .models import Activity, Favorite, Quote, Rating, ReadingSession, Review, ShelfEntry


class JalaliTests(TestCase):
    def test_round_trip(self):
        self.assertEqual(to_jalali(datetime.date(2025, 3, 21)), (1404, 1, 1))
        self.assertEqual(from_jalali(1403, 12, 30), datetime.date(2025, 3, 20))  # ۱۴۰۳ کبیسه است
        with self.assertRaises(ValueError):
            from_jalali(1404, 7, 31)  # مهر ۳۰ روزه است

    def test_form_field_accepts_persian_digits(self):
        self.assertEqual(JalaliDateField().clean("۱۴۰۴/۰۱/۰۱"), datetime.date(2025, 3, 21))


class BaseData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = Category.objects.create(name="رمان", slug="roman")
        cls.author = Author.objects.create(name="نویسنده‌ی تست")
        cls.book = Book.objects.create(title="کتاب تست", author=cls.author, category=cls.cat, pages=100)
        cls.other = Book.objects.create(title="کتاب دوم", author=cls.author, category=cls.cat, pages=50)
        cls.user = User.objects.create_user("member", password="pass12345", first_name="عضو")
        cls.admin = User.objects.create_user("boss", password="pass12345", is_staff=True)


class ReadingFlowTests(BaseData):
    def setUp(self):
        self.client.force_login(self.user)

    def test_session_moves_book_to_reading_then_read(self):
        url = reverse("reading:session_create")
        today = to_jalali(datetime.date.today())
        date = "/".join(str(x) for x in today)
        self.client.post(url, {"book": self.book.pk, "date": date, "minutes": 30, "start_page": 0, "end_page": 40})
        entry = ShelfEntry.objects.get(user=self.user, book=self.book)
        self.assertEqual(entry.status, ShelfEntry.Status.READING)
        self.assertEqual(entry.current_page, 40)

        self.client.post(url, {"book": self.book.pk, "date": date, "minutes": 50, "start_page": 40, "end_page": 100})
        entry.refresh_from_db()
        self.assertEqual(entry.status, ShelfEntry.Status.READ)
        self.assertEqual(entry.finished_on, datetime.date.today())
        self.assertTrue(Activity.objects.filter(user=self.user, verb=Activity.Verb.FINISHED).exists())

    def test_session_rejects_future_date_and_bad_pages(self):
        future = to_jalali(datetime.date.today() + datetime.timedelta(days=3))
        response = self.client.post(reverse("reading:session_create"), {
            "book": self.book.pk, "date": "/".join(map(str, future)), "minutes": 10, "start_page": 50, "end_page": 20})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReadingSession.objects.exists())

    def test_rate_favorite_status(self):
        self.client.post(reverse("reading:rate", args=[self.book.pk]), {"score": 4})
        self.assertEqual(Rating.objects.get(user=self.user, book=self.book).score, 4)
        self.client.post(reverse("reading:rate", args=[self.book.pk]), {"score": 9})  # نامعتبر
        self.assertEqual(Rating.objects.get(user=self.user, book=self.book).score, 4)

        self.client.post(reverse("reading:toggle_favorite", args=[self.book.pk]))
        self.assertTrue(Favorite.objects.filter(user=self.user, book=self.book).exists())
        self.client.post(reverse("reading:toggle_favorite", args=[self.book.pk]))
        self.assertFalse(Favorite.objects.filter(user=self.user, book=self.book).exists())

        self.client.post(reverse("reading:set_status", args=[self.book.pk]), {"status": "read"})
        self.assertEqual(ShelfEntry.objects.get(user=self.user, book=self.book).progress, 100)

    def test_review_and_quote(self):
        self.client.post(reverse("reading:review_edit", args=[self.book.pk]),
                         {"title": "عالی", "body": "این کتاب واقعاً خواندنی بود و پیشنهادش می‌کنم."})
        self.assertEqual(Review.objects.filter(book=self.book).count(), 1)
        self.client.post(reverse("reading:quote_create"),
                         {"book": self.book.pk, "kind": "quote", "text": "جمله‌ی مهم", "page": 12, "is_public": "on"})
        self.assertEqual(Quote.objects.get().page, 12)

    def test_cannot_edit_other_users_session(self):
        session = ReadingSession.objects.create(user=self.admin, book=self.book, minutes=10)
        response = self.client.get(reverse("reading:session_edit", args=[session.pk]))
        self.assertEqual(response.status_code, 404)


class AccessTests(BaseData):
    def test_guest_pages(self):
        for name, args in [("core:home", []), ("catalog:book_list", []), ("catalog:book_detail", [self.book.pk]),
                           ("catalog:author_list", []), ("catalog:category_list", []), ("core:quote_feed", []),
                           ("accounts:login", []), ("accounts:register", []), ("core:profile", ["member"])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_guest_redirected_from_member_pages(self):
        for name in ["reading:shelf", "reading:stats", "reading:session_list", "reading:quote_list"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)

    def test_member_cannot_open_panel(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 302)

    def test_member_pages(self):
        self.client.force_login(self.user)
        ReadingSession.objects.create(user=self.user, book=self.book, minutes=25, pages_read=10)
        for name in ["core:home", "reading:shelf", "reading:session_list", "reading:quote_list", "reading:stats",
                     "accounts:profile_edit"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        for params in ["?range=7", "?range=365", "?range=year", "?range=custom&start=1404/01/01&end=1404/06/31",
                       "?range=custom&start=bad&end=1"]:
            self.assertEqual(self.client.get(reverse("reading:stats") + params).status_code, 200, params)

    def test_admin_pages(self):
        self.client.force_login(self.admin)
        ReadingSession.objects.create(user=self.user, book=self.book, minutes=25, pages_read=10)
        for name, args in [("panel:dashboard", []), ("panel:book_list", []), ("panel:book_create", []),
                           ("panel:book_edit", [self.book.pk]), ("panel:author_list", []), ("panel:category_list", []),
                           ("panel:user_list", []), ("panel:user_detail", [self.user.pk]), ("panel:review_list", []),
                           ("panel:activity_list", []), ("panel:reports", [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        for sort in ["minutes", "recent", "joined", "read"]:
            self.assertEqual(self.client.get(reverse("panel:user_list") + f"?sort={sort}").status_code, 200)
        response = self.client.get(reverse("panel:reports_export") + "?range=30")
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("کتاب تست", response.content.decode("utf-8"))

    def test_admin_can_delete_book_but_not_used_author(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:author_delete", args=[self.author.pk]))
        self.assertTrue(Author.objects.filter(pk=self.author.pk).exists())  # PROTECT
        self.client.post(reverse("panel:book_delete", args=[self.other.pk]))
        self.assertFalse(Book.objects.filter(pk=self.other.pk).exists())

    def test_private_profile_hidden(self):
        self.user.profile.is_public = False
        self.user.profile.save()
        response = self.client.get(reverse("core:profile", args=["member"]))
        self.assertContains(response, "خصوصی")

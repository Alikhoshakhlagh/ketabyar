"""
ساخت داده‌ی نمونه برای ارائه و تست:
    python manage.py seed_demo           # اگر دیتابیس خالی باشد
    python manage.py seed_demo --reset   # پاک کردن همه‌چیز و ساخت دوباره

نام‌های کاربری و رمزهای نمونه در README.md نوشته شده‌اند.
"""
import datetime
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import Author, Book, Category
from reading.models import (Activity, Favorite, Quote, Rating, ReadingSession, Review, ReviewLike,
                            ShelfEntry)

DEMO_PASSWORD = "ketab1234"
ADMIN_PASSWORD = "admin1234"

CATEGORIES = [
    ("رمان", "roman", "#2F6F5E", "داستان‌های بلند ایرانی و جهان"),
    ("ادبیات کلاسیک فارسی", "classic", "#8C5A2B", "نثر و نظم کهن فارسی"),
    ("شعر", "poetry", "#B0476A", "دیوان‌ها و مجموعه‌های شعر"),
    ("تاریخ", "history", "#6B5B95", "تاریخ ایران و جهان"),
    ("روان‌شناسی", "psychology", "#2B6CB0", "شناخت ذهن و رفتار انسان"),
    ("فلسفه", "philosophy", "#4A5568", "پرسش‌های بنیادین درباره‌ی هستی و انسان"),
    ("علمی‌تخیلی", "scifi", "#0F766E", "آینده، فناوری و جهان‌های دیگر"),
    ("کودک و نوجوان", "kids", "#D97706", "کتاب‌هایی برای همه‌ی سنین"),
]

AUTHORS = [
    ("سعدی", "ایران"), ("حافظ", "ایران"), ("مولوی", "ایران"), ("فردوسی", "ایران"), ("خیام", "ایران"),
    ("صادق هدایت", "ایران"), ("محمود دولت‌آبادی", "ایران"), ("سیمین دانشور", "ایران"), ("جلال آل‌احمد", "ایران"),
    ("هوشنگ گلشیری", "ایران"), ("احمد محمود", "ایران"), ("صمد بهرنگی", "ایران"), ("عبدالحسین زرین‌کوب", "ایران"),
    ("فئودور داستایفسکی", "روسیه"), ("لئو تولستوی", "روسیه"), ("جورج اورول", "بریتانیا"), ("آلبر کامو", "فرانسه"),
    ("فرانتس کافکا", "چک"), ("گابریل گارسیا مارکز", "کلمبیا"), ("ویکتور فرانکل", "اتریش"),
    ("یووال نوح هراری", "اسرائیل"), ("آنتوان دو سنت‌اگزوپری", "فرانسه"), ("ری بردبری", "آمریکا"),
    ("آیزاک آسیموف", "آمریکا"), ("افلاطون", "یونان"), ("یوستین گردر", "نروژ"), ("اروین یالوم", "آمریکا"),
]

# (عنوان، نویسنده، مترجم، دسته، سال، صفحات، کیفیت ۱ تا ۵، معرفی)
BOOKS = [
    ("گلستان", "سعدی", "", "classic", 1398, 320, 4.8, "شاهکار نثر مسجع فارسی در هشت باب؛ حکایت‌هایی کوتاه درباره‌ی اخلاق، سیاست و زندگی که پس از قرن‌ها هنوز تازه‌اند."),
    ("بوستان", "سعدی", "", "classic", 1397, 410, 4.6, "منظومه‌ی تعلیمی سعدی در ده باب، درباره‌ی عدل، احسان، عشق، تواضع و تربیت."),
    ("دیوان حافظ", "حافظ", "", "poetry", 1399, 560, 4.9, "غزل‌های لسان‌الغیب؛ کتابی که در خانه‌ی بیشتر ایرانی‌ها پیدا می‌شود."),
    ("مثنوی معنوی", "مولوی", "", "poetry", 1396, 1100, 4.7, "دریای حکایت و اندیشه‌ی عرفانی در شش دفتر."),
    ("شاهنامه", "فردوسی", "", "classic", 1394, 1450, 4.8, "حماسه‌ی ملی ایرانیان؛ از پادشاهی کیومرث تا پایان ساسانیان."),
    ("رباعیات خیام", "خیام", "", "poetry", 1400, 140, 4.5, "رباعی‌هایی کوتاه درباره‌ی گذر عمر، شادی و پرسش‌های بی‌پاسخ."),
    ("بوف کور", "صادق هدایت", "", "roman", 1351, 120, 4.1, "مشهورترین رمان مدرن فارسی؛ روایتی کابوس‌وار و درونی از تنهایی و مرگ."),
    ("جای خالی سلوچ", "محمود دولت‌آبادی", "", "roman", 1357, 430, 4.4, "داستان زنی روستایی به نام مرگان که پس از ناپدید شدن شوهرش، بار زندگی را به دوش می‌کشد."),
    ("کلیدر", "محمود دولت‌آبادی", "", "roman", 1363, 2800, 4.5, "رمان سترگ ده‌جلدی درباره‌ی زندگی ایلیاتی و گل‌محمد در خراسان."),
    ("سووشون", "سیمین دانشور", "", "roman", 1348, 300, 4.5, "روایت زری و یوسف در شیراز سال‌های اشغال؛ یکی از پرفروش‌ترین رمان‌های فارسی."),
    ("مدیر مدرسه", "جلال آل‌احمد", "", "roman", 1337, 140, 3.9, "داستان کوتاه و طنزآمیز معلمی که مدیر یک مدرسه‌ی دورافتاده می‌شود."),
    ("شازده احتجاب", "هوشنگ گلشیری", "", "roman", 1348, 110, 4.0, "آخرین بازمانده‌ی یک خاندان قاجاری در شبی بلند، گذشته را مرور می‌کند."),
    ("همسایه‌ها", "احمد محمود", "", "roman", 1353, 480, 4.2, "نوجوانی خالد در اهواز دهه‌ی سی و بیدار شدن آگاهی سیاسی‌اش."),
    ("ماهی سیاه کوچولو", "صمد بهرنگی", "", "kids", 1347, 48, 4.4, "ماهی کوچکی که می‌خواهد ببیند آخر جویبار کجاست."),
    ("دو قرن سکوت", "عبدالحسین زرین‌کوب", "", "history", 1330, 380, 4.3, "تاریخ دو قرن نخست پس از ورود اسلام به ایران، با نثری ادبی و گیرا."),
    ("جنایت و مکافات", "فئودور داستایفسکی", "مهری آهی", "roman", 1866, 720, 4.7, "راسکولنیکف، دانشجوی فقیر سن‌پترزبورگ، جنایتی مرتکب می‌شود و بار وجدانش را می‌کشد."),
    ("برادران کارامازوف", "فئودور داستایفسکی", "صالح حسینی", "roman", 1880, 1100, 4.8, "سه برادر و پدری خودخواه؛ رمانی درباره‌ی ایمان، شک و آزادی."),
    ("جنگ و صلح", "لئو تولستوی", "سروش حبیبی", "roman", 1869, 1900, 4.6, "زندگی چند خانواده‌ی اشرافی روس در سال‌های جنگ با ناپلئون."),
    ("آنا کارنینا", "لئو تولستوی", "سروش حبیبی", "roman", 1878, 1050, 4.6, "عشقی ممنوع در جامعه‌ی اشرافی روسیه و بهایی که برای آن پرداخته می‌شود."),
    ("۱۹۸۴", "جورج اورول", "صالح حسینی", "scifi", 1949, 380, 4.6, "جهانی که در آن «برادر بزرگ» همه‌چیز را می‌بیند و حقیقت هر روز بازنویسی می‌شود."),
    ("قلعه‌ی حیوانات", "جورج اورول", "امیر امیرشاهی", "roman", 1945, 120, 4.4, "حیوانات مزرعه انقلاب می‌کنند، اما «همه برابرند، ولی بعضی برابرترند»."),
    ("بیگانه", "آلبر کامو", "جلال آل‌احمد، اصغر خبره‌زاده", "roman", 1942, 150, 4.2, "مورسو، مردی بی‌اعتنا به قراردادهای اجتماعی، در برابر دادگاه و جهان."),
    ("طاعون", "آلبر کامو", "رضا سیدحسینی", "roman", 1947, 380, 4.3, "شهر اوران در قرنطینه؛ داستانی درباره‌ی همبستگی انسانی در برابر فاجعه."),
    ("مسخ", "فرانتس کافکا", "صادق هدایت", "roman", 1915, 90, 4.2, "گرگور سامسا یک روز صبح بیدار می‌شود و می‌بیند به حشره‌ای بزرگ تبدیل شده است."),
    ("صد سال تنهایی", "گابریل گارسیا مارکز", "بهمن فرزانه", "roman", 1967, 520, 4.6, "حماسه‌ی هفت نسل از خاندان بوئندیا در شهر خیالی ماکوندو."),
    ("انسان در جست‌وجوی معنا", "ویکتور فرانکل", "نهضت صالحیان، مهین میلانی", "psychology", 1946, 210, 4.7, "تجربه‌ی روان‌پزشکی در اردوگاه‌های کار اجباری و نظریه‌ی معنادرمانی."),
    ("انسان خردمند", "یووال نوح هراری", "نیک گرگین", "history", 2011, 560, 4.3, "تاریخ مختصر بشر از انقلاب شناختی تا انقلاب علمی."),
    ("شازده کوچولو", "آنتوان دو سنت‌اگزوپری", "احمد شاملو", "kids", 1943, 110, 4.8, "شاهزاده‌ای کوچک از سیاره‌ای دور، درباره‌ی دوستی و آنچه با چشم دیده نمی‌شود."),
    ("فارنهایت ۴۵۱", "ری بردبری", "", "scifi", 1953, 230, 4.1, "آینده‌ای که در آن مأموران آتش‌نشانی به‌جای خاموش کردن آتش، کتاب‌ها را می‌سوزانند."),
    ("بنیاد", "آیزاک آسیموف", "", "scifi", 1951, 290, 4.2, "ریاضی‌دانی سقوط امپراتوری کهکشانی را پیش‌بینی می‌کند و برای کوتاه کردن دوران تاریکی نقشه می‌کشد."),
    ("جمهور", "افلاطون", "فؤاد روحانی", "philosophy", 1353, 620, 4.2, "گفت‌وگوهای سقراط درباره‌ی عدالت و شهر آرمانی."),
    ("دنیای سوفی", "یوستین گردر", "حسن کامشاد", "philosophy", 1991, 580, 4.4, "تاریخ فلسفه در قالب رمانی جذاب برای نوجوانان و بزرگسالان."),
    ("وقتی نیچه گریست", "اروین یالوم", "", "psychology", 1992, 470, 4.4, "رمانی خیالی درباره‌ی دیدار نیچه و دکتر برویر در وین قرن نوزدهم."),
]

# نقل‌قول‌ها فقط از متن‌های کلاسیک فارسی (مالکیت عمومی)
QUOTES = {
    "گلستان": [
        ("بنی‌آدم اعضای یکدیگرند\nکه در آفرینش ز یک گوهرند", 45),
        ("دو چیز طیره‌ی عقل است: دم فروبستن به وقت گفتن و گفتن به وقت خاموشی.", 187),
        ("مشک آن است که خود ببوید، نه آن‌که عطار بگوید.", 230),
    ],
    "بوستان": [("به نام خداوند جان‌آفرین\nحکیم سخن در زبان‌آفرین", 1)],
    "دیوان حافظ": [
        ("صلاح کار کجا و من خراب کجا\nببین تفاوت ره کز کجاست تا به کجا", 12),
        ("یوسف گم‌گشته بازآید به کنعان غم مخور\nکلبه‌ی احزان شود روزی گلستان غم مخور", 230),
    ],
    "مثنوی معنوی": [
        ("بشنو این نی چون شکایت می‌کند\nاز جدایی‌ها حکایت می‌کند", 1),
        ("هر کسی کو دور ماند از اصل خویش\nباز جوید روزگار وصل خویش", 1),
    ],
    "شاهنامه": [
        ("توانا بود هر که دانا بود\nز دانش دل پیر برنا بود", 3),
        ("بسی رنج بردم در این سال سی\nعجم زنده کردم بدین پارسی", 1420),
    ],
    "رباعیات خیام": [
        ("این قافله‌ی عمر عجب می‌گذرد\nدریاب دمی که با طرب می‌گذرد", 22),
        ("از دی که گذشت هیچ از او یاد مکن\nفردا که نیامده است فریاد مکن", 35),
    ],
}

REVIEWS = {
    "good": [
        ("شاهکاری که باید خواند", "یکی از بهترین کتاب‌هایی که امسال خواندم. شخصیت‌پردازی دقیق و نثر روانش باعث شد نتوانم زمینش بگذارم و چند شب تا دیروقت بیدار ماندم."),
        ("بار دوم، باز هم شگفت‌انگیز", "بار دوم است که این کتاب را می‌خوانم و باز هم نکته‌های تازه‌ای پیدا کردم. خواندنش را به همه، به‌خصوص کسانی که تازه کتاب‌خوانی را شروع کرده‌اند، پیشنهاد می‌کنم."),
        ("آرام شروع می‌شود، رهایت نمی‌کند", "روایت کتاب آرام شروع می‌شود اما از نیمه به بعد کاملاً درگیرتان می‌کند. پایان‌بندی‌اش تا چند روز در ذهنم بود."),
        ("خوش‌خوان و عمیق", "ترجمه‌ی خوبی داشت و متن خیلی خوش‌خوان بود. فصل‌های پایانی را در یک نشست خواندم و بعدش مدتی فقط به آن فکر می‌کردم."),
    ],
    "mid": [
        ("خوب، ولی کمی طولانی", "ایده‌ی اصلی کتاب جذاب است ولی بخش‌های میانی کمی طولانی شده‌اند. با این حال ارزش یک بار خواندن را دارد."),
        ("متوسط اما ارزشمند", "برای من کتاب متوسطی بود؛ بعضی فصل‌ها فوق‌العاده بودند و بعضی را به‌سختی تمام کردم. فکر می‌کنم در سن دیگری لذت بیشتری می‌بردم."),
    ],
    "bad": [
        ("انتظار بیشتری داشتم", "با این همه تعریفی که شنیده بودم انتظار بیشتری داشتم. ریتم کتاب برایم کند بود و نتوانستم با شخصیت‌ها ارتباط برقرار کنم."),
    ],
    "spoiler": [
        ("پایانی که غافلگیرم کرد", "تصمیم شخصیت اصلی در فصل آخر کاملاً غافلگیرم کرد؛ تمام نشانه‌ها از اول کتاب جلوی چشمم بود و ندیده بودمشان. وقتی فهمیدم چه کسی پشت ماجرا بوده، برگشتم و فصل اول را دوباره خواندم."),
    ],
}

USERS = [
    # (نام کاربری، نام، نام خانوادگی، کتاب در سال، دقیقه‌ی میانگین، صفحه در ساعت، احتمال مطالعه در روز، دسته‌های محبوب)
    ("sara", "سارا", "احمدی", 24, 45, 38, 0.85, ["roman", "psychology"]),
    ("ali", "علی", "رضایی", 12, 35, 30, 0.55, ["history", "philosophy", "scifi"]),
    ("maryam", "مریم", "کریمی", 30, 55, 42, 0.75, ["roman", "classic", "poetry"]),
    ("reza", "رضا", "محمدی", 8, 25, 26, 0.4, ["scifi", "roman"]),
    ("neda", "ندا", "حسینی", 18, 40, 35, 0.65, ["poetry", "classic", "kids"]),
    ("hamed", "حامد", "نوری", 10, 30, 28, 0.45, ["philosophy", "psychology"]),
    ("zahra", "زهرا", "موسوی", 15, 35, 33, 0.6, ["roman", "history"]),
    ("kian", "کیان", "صادقی", 6, 20, 24, 0.3, ["kids", "scifi"]),
]


def _stamp(model_obj, when):
    """زمان ثبت (auto_now_add) را به تاریخ دلخواه برمی‌گرداند."""
    dt = timezone.make_aware(datetime.datetime.combine(when, datetime.time(random.randint(7, 23), random.randint(0, 59))))
    type(model_obj).objects.filter(pk=model_obj.pk).update(created_at=dt)
    return dt


class Command(BaseCommand):
    help = "ساخت داده‌ی نمونه (کتاب‌ها، کاربران و چند ماه سابقه‌ی مطالعه)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="پاک کردن داده‌های قبلی")
        parser.add_argument("--days", type=int, default=180, help="چند روز سابقه‌ی مطالعه ساخته شود")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(1405)
        if options["reset"]:
            for model in (Activity, ReviewLike, Review, Rating, Favorite, Quote, ReadingSession, ShelfEntry, Book,
                          Author, Category):
                model.objects.all().delete()
            User.objects.filter(username__in=[u[0] for u in USERS] + ["admin"]).delete()
        elif Book.objects.exists():
            self.stdout.write(self.style.WARNING("دیتابیس خالی نیست. برای ساخت دوباره از --reset استفاده کنید."))
            return

        today = datetime.date.today()
        days = options["days"]

        cats = {slug: Category.objects.create(name=n, slug=slug, color=c, description=d) for n, slug, c, d in CATEGORIES}
        authors = {n: Author.objects.create(name=n, country=c) for n, c in AUTHORS}

        admin = User.objects.create_superuser("admin", "admin@ketabyar.local", ADMIN_PASSWORD,
                                              first_name="مدیر", last_name="سامانه")
        admin.profile.bio = "مدیر سامانه‌ی کتاب‌یار"
        admin.profile.save()

        books, quality = [], {}
        for title, author, translator, cat, year, pages, q, desc in BOOKS:
            book = Book.objects.create(title=title, author=authors[author], translator=translator, category=cats[cat],
                                       publish_year=year, pages=pages, description=desc, created_by=admin)
            books.append(book)
            quality[book.pk] = q

        users = []
        for username, first, last, goal, avg_min, speed, prob, fav_cats in USERS:
            user = User.objects.create_user(username, f"{username}@example.com", DEMO_PASSWORD,
                                            first_name=first, last_name=last)
            user.profile.yearly_goal = goal
            user.profile.daily_goal_minutes = max(20, avg_min)
            user.profile.bio = f"عاشق {'، '.join(cats[c].name for c in fav_cats)}"
            user.profile.is_public = username != "kian"
            user.profile.save()
            joined = today - datetime.timedelta(days=days + random.randint(5, 60))
            User.objects.filter(pk=user.pk).update(date_joined=timezone.make_aware(
                datetime.datetime.combine(joined, datetime.time(10))))
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.JOINED), joined)
            users.append(user)
            self._simulate(user, books, quality, cats, fav_cats, avg_min, speed, prob, today, days)
            self._extra_quotes(user, books, today)

        self._likes(users)
        self.stdout.write(self.style.SUCCESS(
            f"ساخته شد: {Book.objects.count()} کتاب، {User.objects.count()} کاربر، "
            f"{ReadingSession.objects.count()} جلسه‌ی مطالعه، {Review.objects.count()} نقد، {Quote.objects.count()} نقل‌قول"))

    # ------------------------------------------------------------------
    def _simulate(self, user, books, quality, cats, fav_cats, avg_min, speed, prob, today, days):
        """یک کاربر را روز به روز شبیه‌سازی می‌کند: کتاب برمی‌دارد، می‌خواند، تمام می‌کند، امتیاز می‌دهد."""
        fav_ids = {cats[c].pk for c in fav_cats}
        pool = sorted(books, key=lambda b: (b.category_id not in fav_ids, random.random()))
        pool = [b for b in pool if b.pages <= 1200 or random.random() < 0.3]
        weekday_bias = {wd: random.uniform(0.6, 1.4) for wd in range(7)}
        start = today - datetime.timedelta(days=days)
        is_sara = user.username == "sara"

        current, page = None, 0
        queue = list(pool)
        sessions = []

        def finish(book, on):
            entry = ShelfEntry.objects.get(user=user, book=book)
            entry.status, entry.current_page, entry.finished_on = ShelfEntry.Status.READ, book.pages, on
            entry.save()
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.FINISHED, book=book), on)
            self._react(user, book, quality[book.pk], on)

        def pick(on):
            book = queue.pop(0)
            ShelfEntry.objects.create(user=user, book=book, status=ShelfEntry.Status.READING, started_on=on)
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.SHELF, book=book, detail="در حال مطالعه"), on)
            return book

        day = start
        while day <= today and queue:
            if current is None:
                current, page = pick(day), 0
            recent = is_sara and (today - day).days < 14
            if recent or random.random() < prob * weekday_bias[day.weekday()]:
                minutes = max(5, int(random.gauss(avg_min, avg_min * 0.35)))
                pages_read = max(1, round(minutes * speed / 60 * random.uniform(0.8, 1.2)))
                end = min(current.pages, page + pages_read)
                sessions.append(ReadingSession(user=user, book=current, date=day, minutes=minutes, start_page=page,
                                               end_page=end, pages_read=end - page))
                page = end
                if page >= current.pages:
                    finish(current, day)
                    current = None
                elif random.random() < 0.004:  # گاهی کتاب نیمه‌کاره کنار گذاشته می‌شود
                    ShelfEntry.objects.filter(user=user, book=current).update(
                        status=ShelfEntry.Status.TO_READ, current_page=page)
                    current = None
            day += datetime.timedelta(days=1)

        ReadingSession.objects.bulk_create(sessions)
        if current is not None:
            ShelfEntry.objects.filter(user=user, book=current).update(current_page=page)
        # هر کاربر در پایان، یک یا دو کتاب نیمه‌خوانده دارد تا پیشخوانش خالی نباشد
        while queue and ShelfEntry.objects.filter(user=user, status=ShelfEntry.Status.READING).count() < 2:
            book = pick(today - datetime.timedelta(days=random.randint(3, 20)))
            first_page = round(book.pages * random.uniform(0.15, 0.55))
            ReadingSession.objects.create(user=user, book=book, date=today - datetime.timedelta(days=1),
                                          minutes=avg_min, start_page=0, end_page=first_page)
            ShelfEntry.objects.filter(user=user, book=book).update(current_page=first_page)
        # آخرین جلسه‌ها در لاگ فعالیت
        for s in sessions[-6:]:
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.SESSION, book=s.book,
                                           detail=f"{s.minutes} دقیقه"), s.date)
        # چند کتاب برای «برنامه‌ریزی برای مطالعه»
        for book in queue[:random.randint(2, 5)]:
            entry = ShelfEntry.objects.create(user=user, book=book, status=ShelfEntry.Status.TO_READ)
            ShelfEntry.objects.filter(pk=entry.pk).update(
                created_at=timezone.now() - datetime.timedelta(days=random.randint(1, 60)))

    def _react(self, user, book, q, on):
        """واکنش بعد از تمام کردن کتاب: امتیاز، گاهی نقد، علاقه‌مندی و نقل‌قول"""
        score = max(1, min(5, round(random.gauss(q, 0.7))))
        _stamp(Rating.objects.create(user=user, book=book, score=score), on)
        if random.random() < 0.65:
            if random.random() < 0.12:
                kind = "spoiler"
            else:
                kind = "good" if score >= 4 else ("mid" if score == 3 else "bad")
            title, body = random.choice(REVIEWS[kind])
            review = Review.objects.create(user=user, book=book, title=title, body=body, has_spoiler=kind == "spoiler")
            _stamp(review, on + datetime.timedelta(days=random.randint(0, 3)))
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.REVIEWED, book=book, detail=title), on)
        if score == 5 and random.random() < 0.7:
            _stamp(Favorite.objects.create(user=user, book=book), on)
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.FAVORITED, book=book), on)
        if book.title in QUOTES and random.random() < 0.8:
            text, page = random.choice(QUOTES[book.title])
            kind = Quote.Kind.HIGHLIGHT if random.random() < 0.3 else Quote.Kind.QUOTE
            note = random.choice(["", "", "این بیت را باید حفظ کنم.", "یادآوری برای روزهای سخت."])
            _stamp(Quote.objects.create(user=user, book=book, text=text, page=page, kind=kind, note=note), on)
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.QUOTED, book=book, detail=text[:60]), on)

    def _extra_quotes(self, user, books, today):
        """هر کاربر چند نقل‌قول از متن‌های کلاسیک هم ثبت کرده است"""
        by_title = {b.title: b for b in books}
        for title in random.sample(list(QUOTES), random.randint(1, 3)):
            text, page = random.choice(QUOTES[title])
            if Quote.objects.filter(user=user, text=text).exists():
                continue
            on = today - datetime.timedelta(days=random.randint(0, 120))
            quote = Quote.objects.create(user=user, book=by_title[title], text=text, page=page,
                                         kind=random.choice([Quote.Kind.QUOTE, Quote.Kind.QUOTE, Quote.Kind.HIGHLIGHT]))
            _stamp(quote, on)
            _stamp(Activity.objects.create(user=user, verb=Activity.Verb.QUOTED, book=quote.book, detail=text[:60]), on)

    def _likes(self, users):
        for review in Review.objects.all():
            for user in random.sample(users, random.randint(0, 4)):
                if user != review.user:
                    ReviewLike.objects.get_or_create(user=user, review=review)

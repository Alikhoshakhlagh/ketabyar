-- ساخت کاربر و دیتابیس PostgreSQL برای کتاب‌یار
-- اجرا:  psql -U postgres -h localhost -p 5433 -f setup_db.sql
-- قبل از اجرا، رمز زیر را عوض کنید و همان را در فایل .env بنویسید.

CREATE USER ketabyar WITH PASSWORD 'change-me';
CREATE DATABASE ketabyar OWNER ketabyar ENCODING 'UTF8' TEMPLATE template0;
GRANT ALL PRIVILEGES ON DATABASE ketabyar TO ketabyar;

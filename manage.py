#!/usr/bin/env python
"""ابزار خط فرمان جنگو برای پروژه‌ی کتاب‌یار."""
import os
import sys


def main():
    # کنسول ویندوز به‌صورت پیش‌فرض نمی‌تواند همه‌ی حروف فارسی را چاپ کند
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

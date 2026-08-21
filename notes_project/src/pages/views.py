from django.db import connection
from django.shortcuts import redirect, render

from .models import Note, User


def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")

        # Flaw 1 (A04:2025 Cryptographic Failures / A07:2025 Authentication Failures)
        # The password is stored as a plain text not encrypted in any way
        user = User.objects.create(username=username, password=password)

        # Fix:
        # from django.contrib.auth.hashers import make_password
        # user = User.objects.create(username=username, password=make_password(password))

        request.session["user_id"] = user.id
        return redirect("index")
    return render(request, "pages/register.html")


def login_view(request):
    # Flaw 2 (A07:2025 Authentication Failures)
    # There is no block against brute forcing the password
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")

        # Plain string filtering
        user = User.objects.filter(username=username, password=password).first()

        # Fix to Flaw 1:
        # from django.contrib.auth.hashers import check_password
        # user = User.objects.filter(username=username).first()
        # if user and not check_password(password, user.password):
        #     user = None

        # Fix to Flaw 2:
        # from django.core.cache import cache
        # cache_key = f"login_attempts_{username}"
        # attempts = cache.get(cache_key, 0)
        # if attempts >= 5:
        #     error = "Too many login attempts. Please try again later."
        if user:
            request.session["user_id"] = user.id
            return redirect("index")
        error = "Invalid username or password"
    return render(request, "pages/login.html", {"error": error})


def logout_view(request):
    request.session.flush()
    return redirect("login")


def index(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("login")
    me = User.objects.get(id=user_id)

    if request.method == "POST":
        Note.objects.create(
            owner=me,
            title=request.POST.get("title", ""),
            body=request.POST.get("body", ""),
        )
        return redirect("index")

    query = request.GET.get("q", "")
    if query:
        # Flaw 2 (A05:2025 Injection - SQL injection)
        # The note search box is in raw SQL
        # For example: "x' UNION SELECT id, username || ':' || password FROM pages_user--" returns
        # all users and their passwords
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, title FROM pages_note WHERE title LIKE '%%%s%%'" % query)
            notes = [{"id": row[0], "title": row[1]} for row in cursor.fetchall()]

        # Fix:
        # notes = Note.objects.filter(owner=me, title__icontains=query).values("id", "title")
    else:
        notes = Note.objects.filter(owner=me).values("id", "title")

    return render(request, "pages/index.html", {"me": me, "notes": notes, "query": query})


def note_detail(request, pk):
    if not request.session.get("user_id"):
        return redirect("login")

    # Flaw 4 (A01:2025 Broken Access Control)
    # Any logged in user can read any note just by changing the id in the URL
    # There's no check that note.owner matches the session user
    note = Note.objects.filter(pk=pk).first()

    # Fix:
    # me_id = request.session["user_id"]
    # note = Note.objects.filter(pk=pk, owner_id=me_id).first()

    return render(request, "pages/note.html", {"note": note})

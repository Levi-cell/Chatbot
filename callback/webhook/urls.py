from django.urls import path
# from django.contrib import admin
from .views import callback

urlpatterns = [
    path("webhook/", callback),
    # path("admin/", admin.site.urls),
]
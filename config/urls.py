from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Core app (all your pages)
    path('', include('core.urls')),
]
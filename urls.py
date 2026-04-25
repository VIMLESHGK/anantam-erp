from django.contrib import admin
from django.urls import path, include
from . import views


urlpatterns = [
    path('core/', include('core.urls'))
     path('', views.home, name='home'),  # IMPORTANT
    path('dashboard/', views.dashboard, name='dashboard'),
    path('customers/', views.customers, name='customers'),
    path('admin/', admin.site.urls),
]

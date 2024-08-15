from django.urls import path, include

from . import views

from rest_framework.authtoken.views import obtain_auth_token
from rest_framework import routers

router = routers.DefaultRouter()

urlpatterns = [
    path('kaspi-payment/', views.Kaspi.as_view(), name="kaspi")
]

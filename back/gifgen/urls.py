from django.urls import path
from .views import GenerateGIFAPIView

urlpatterns = [
    path('generate_gif/', GenerateGIFAPIView.as_view(), name='generate_gif'),
]

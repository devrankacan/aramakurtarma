from django.urls import path

from .views import KnowledgeBaseListView

urlpatterns = [
    path("bilgi-bankasi/", KnowledgeBaseListView.as_view(), name="knowledge_base"),
]

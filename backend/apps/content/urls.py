from django.urls import path

from .views import AnnouncementDetailView, AnnouncementListView, KnowledgeBaseListView

urlpatterns = [
    path("bilgi-bankasi/", KnowledgeBaseListView.as_view(), name="knowledge_base"),
    path("duyurular/", AnnouncementListView.as_view(), name="announcements"),
    path("duyurular/<int:pk>/", AnnouncementDetailView.as_view(), name="announcement_detail"),
]

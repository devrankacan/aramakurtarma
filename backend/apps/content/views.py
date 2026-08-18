from django.utils import timezone
from django.views.generic import DetailView, ListView

from .models import Announcement, DisasterNewsItem, KnowledgeBaseDocument


class KnowledgeBaseListView(ListView):
    model = KnowledgeBaseDocument
    template_name = "content/knowledge_base.html"
    context_object_name = "documents"

    def get_queryset(self):
        return KnowledgeBaseDocument.objects.filter(is_published=True)


class AnnouncementListView(ListView):
    model = Announcement
    template_name = "content/announcements.html"
    context_object_name = "announcements"

    def get_queryset(self):
        return Announcement.objects.filter(
            is_published=True, published_at__lte=timezone.now()
        )


class AnnouncementDetailView(DetailView):
    model = Announcement
    template_name = "content/announcement_detail.html"
    context_object_name = "announcement"

    def get_queryset(self):
        return Announcement.objects.filter(
            is_published=True, published_at__lte=timezone.now()
        )


class DisasterNewsDetailView(DetailView):
    model = DisasterNewsItem
    template_name = "content/disaster_news_detail.html"
    context_object_name = "news_item"

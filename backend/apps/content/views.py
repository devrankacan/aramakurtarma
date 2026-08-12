from django.views.generic import ListView

from .models import KnowledgeBaseDocument


class KnowledgeBaseListView(ListView):
    model = KnowledgeBaseDocument
    template_name = "content/knowledge_base.html"
    context_object_name = "documents"

    def get_queryset(self):
        return KnowledgeBaseDocument.objects.filter(is_published=True)

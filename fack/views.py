from __future__ import absolute_import
from django.db.models import Max
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from django.views.generic import ListView, DetailView, TemplateView, CreateView
from .models import Question, Topic
from .forms import SubmitFAQForm

class TopicList(ListView):
    model = Topic
    template_name = "faq/topic_list.html"
    allow_empty = True
    context_object_name = "topics"

    def get_context_data(self, **kwargs):
        data = super(TopicList, self).get_context_data(**kwargs)
        
        # This slightly magical queryset grabs the latest update date for 
        # topic's questions, then the latest date for that whole group.
        # In other words, it's::
        #
        #   max(max(q.updated_on for q in topic.questions) for topic in topics)
        #
        # Except performed in the DB, so quite a bit more efficiant.
        #
        # We can't just do Question.objects.all().aggregate(max('updated_on'))
        # because that'd prevent a subclass from changing the view's queryset
        # (or even model -- this view'll even work with a different model
        # as long as that model has a many-to-one to something called "questions"
        # with an "updated_on" field). So this magic is the price we pay for
        # being generic.
        return data

class TopicDetail(DetailView):
    model = Topic
    template_name = "faq/topic_detail.html"
    context_object_name = "topic"
    
    def get_context_data(self, **kwargs):
        # Include a list of questions this user has access to. If the user is
        # logged in, this includes protected questions. Otherwise, not.
        qs = self.object.questions.active()
        if self.request.user.is_anonymous():
            qs = qs.exclude(protected=True)

        data = super(TopicDetail, self).get_context_data(**kwargs)
        data.update({
            'questions': qs,
        })
        return data

class QuestionDetail(DetailView):
    queryset = Question.objects.active()
    template_name = "faq/question_detail.html"
    
    def get_queryset(self):        
        topic = get_object_or_404(Topic, slug=self.kwargs['topic_slug'])
        
        # Careful here not to hardcode a base queryset. This lets
        # subclassing users re-use this view on a subset of questions, or
        # even on a new model.
        # FIXME: similar logic as above. This should push down into managers.
        qs = super(QuestionDetail, self).get_queryset().filter(topic=topic)
        if self.request.user.is_anonymous():
            qs = qs.exclude(protected=True)
        
        return qs

class SubmitFAQ(CreateView):
    model = Question
    form_class = SubmitFAQForm
    template_name = "faq/submit_question.html"
    success_view_name = "faq_submit_thanks"
    
    def get_form_kwargs(self):
        kwargs = super(SubmitFAQ, self).get_form_kwargs()
        kwargs['instance'] = Question()
        if self.request.user.is_authenticated():
            kwargs['instance'].created_by = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super(SubmitFAQ, self).form_valid(form)
        messages.success(self.request, 
            _("Your question was submitted and will be reviewed by for inclusion in the FAQ."),
            fail_silently=True,
        )
        return response
        
    def get_success_url(self):
        # The superclass version raises ImproperlyConfigered if self.success_url
        # isn't set. Instead of that, we'll try to redirect to a named view.
        if self.success_url:
            return self.success_url
        else:
            return reverse(self.success_view_name)

class SubmitFAQThanks(TemplateView):
    template_name = "faq/submit_thanks.html"

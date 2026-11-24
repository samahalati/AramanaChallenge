from django.urls import path

from supervision import views as v

urlpatterns = [
    path("dashboard", v.Dashboard.as_view()), path("supervisees", v.Supervisees.as_view()), path("supervisees/<int:uid>", v.SuperviseeDetail.as_view()),
    path("meetings", v.Meetings.as_view()), path("meetings/<int:mid>", v.MeetingDetail.as_view()),
    path("reviews", v.Reviews.as_view()), path("reviews/<int:rid>", v.ReviewDetail.as_view()),
    *[path(f"reviews/<int:rid>/{step}", v.ReviewAction.as_view(step=step)) for step in v.ReviewAction.handlers],
    path("corrective-actions/<int:aid>", v.CorrectiveActionDetail.as_view()), path("my-reviews", v.MyReviews.as_view()),
    path("quality-issues", v.Issues.as_view()), path("quality-issues/<int:iid>/resolve", v.IssueAction.as_view()),
    path("quality-issues/<int:iid>/escalate", v.IssueAction.as_view(escalate=True)),
]

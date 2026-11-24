from django.urls import path

from clinical import views as v

urlpatterns = [
    path("clinical/practitioners/<int:pid>/sessions", v.PractitionerSessionsView.as_view()),
    path("clinical/my-clients", v.MyClientsView.as_view()),
    path("clinical/sessions", v.SessionCreateView.as_view()),
    path("clinical/sessions/<int:sid>", v.SessionDetailView.as_view()),
    path("clinical/sessions/<int:sid>/checkin", v.SessionCheckView.as_view()),
    path("clinical/sessions/<int:sid>/checkout", v.SessionCheckView.as_view(out=True)),
    path("referrals/eligible", v.EligibleView.as_view()),
    path("referrals", v.ReferralView.as_view()),
    path("referrals/mine", v.MyReferralsView.as_view()),
]

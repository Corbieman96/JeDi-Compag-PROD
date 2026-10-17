"""Přihlášení — výchozí stránka podle přístupového profilu a role."""

from django.contrib.auth.views import LoginView

from users.services.post_login import default_post_login_url, resolve_post_login_url

SESSION_EXPIRED_NOTICE = (
    "Přihlášení vypršelo kvůli nečinnosti. Přihlaste se znovu."
)


class AppLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        reason = (self.request.GET.get("reason") or self.request.POST.get("reason") or "").strip()
        ctx["session_expired_notice"] = SESSION_EXPIRED_NOTICE if reason == "idle" else ""
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        from waste_docs.services.svoz_matrix_submit_error_log import record_yard_login

        record_yard_login(user=self.request.user)
        return response

    def get_success_url(self):
        return default_post_login_url(self.request.user)

    def get_redirect_url(self):
        redirect_to = super().get_redirect_url()
        if redirect_to:
            return resolve_post_login_url(self.request.user, redirect_to)
        return self.get_success_url()

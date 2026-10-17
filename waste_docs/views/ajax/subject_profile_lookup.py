from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from catalogs.models import NameSubjectProfile


@login_required
def subject_profile_id_by_name(request):
    """name_id (číselník jména) → pk profilu F/P pro modal párů."""
    raw = (request.GET.get("name_id") or "").strip()
    if not raw.isdigit():
        return JsonResponse({"ok": False, "error": "Neplatné jméno subjektu."}, status=400)
    row = NameSubjectProfile.objects.filter(name_id=int(raw)).values("pk").first()
    if not row:
        return JsonResponse({"ok": False, "error": "Subjekt nemá profil F/P v číselníku."}, status=404)
    return JsonResponse({"ok": True, "subject_profile_id": row["pk"]})

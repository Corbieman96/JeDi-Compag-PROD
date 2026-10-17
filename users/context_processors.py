from users.services.access import build_role_access_context


def role_access(request):
    return {"role_access": build_role_access_context(request.user)}

from users.constants import ROLE_ADMIN, ROLE_DISPECER, ROLE_KONTROLOR, ROLE_ZADAVATEL

from users.services.access import app_role



AUDIT_ACTION_LABELS = {

    "create": "Založení požadavku",

    "resubmit": "Znovu odesláno",

    "fix_saved": "Oprava uložena",

    "cancel": "Zrušeno zadavatelem",

    "invoice_approved": "Záloha schválena",

    "invoice_unpaid_overdue": "Nezaplaceno po splatnosti",

    "invoice_rejected": "Záloha zamítnuta",

    "invoice_overdue_auto": "Automaticky označeno po splatnosti",

    "dispatcher_approved": "Schváleno dispečerem",

    "dispatcher_returned": "Vráceno k opravě",

    "dispatcher_requires_reschedule": "Vyžaduje přeplánování",

    "dispatcher_cancelled": "Zrušeno dispečerem",

    "planned_to_rides": "Převedeno na jízdy",

    "planned_from_form": "Naplánováno z formuláře jízdy",

    "status_sync_auto": "Automatická synchronizace stavu",

    "ride_rescheduled_info": "Jízda přeplánována",

    "follow_up_date_set": "Datum navazující činnosti",

}





def role(user) -> str:

    return app_role(user)





def can_submit(user) -> bool:

    r = role(user)

    return user.is_superuser or r in {ROLE_ZADAVATEL, ROLE_ADMIN}





def can_invoice_approve(user) -> bool:

    r = role(user)

    return user.is_superuser or r in {ROLE_KONTROLOR, ROLE_ADMIN}





def can_dispatcher_review(user) -> bool:

    r = role(user)

    return user.is_superuser or r in {ROLE_DISPECER, ROLE_ADMIN}





def can_plan_rides(user) -> bool:

    return can_dispatcher_review(user)

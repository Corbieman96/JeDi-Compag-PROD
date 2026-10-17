from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AppSettings
from users.constants import ROLE_ADMIN, ROLE_DISPECER, ROLE_ZADAVATEL
from users.forms import UserAdminEditForm, access_profile_defaults_for_save
from users.models import UserAccessProfile
from users.services.access import can_manage_dashboard_notes, can_see_all_waste_docs
from users.services.access_profile import get_access_profile
from users.services.nav_visibility import effective_show_dashboard_nav
from users.services.waste_doc_permissions import (
    can_create_pruvodka,
    can_create_pruvodka_dashboard,
    can_delete_all_pruvodky,
)
from users.services.roles import set_user_role

User = get_user_model()


class CatalogContainerPassportRowVisibilityTests(TestCase):
    """Opt-in řádek Pasport kontejnerů na /catalogs/: INHERIT bez SHOW = skryto (ne-superuser)."""

    def test_inherit_hidden_show_visible_for_dispecer(self):
        from catalogs.catalog_nav_registry import SLUG_CONTAINER_PASSPORT
        from users.services.catalog_row_visibility import effective_show_catalog_index_row

        u = User.objects.create_user(username="t_cat_pass_vis", password="x")
        set_user_role(u, ROLE_DISPECER)
        prof = get_access_profile(u)
        prof.nav_catalogs = UserAccessProfile.NavOverride.INHERIT
        prof.catalog_item_nav = {SLUG_CONTAINER_PASSPORT: UserAccessProfile.NavOverride.INHERIT}
        prof.save(update_fields=["nav_catalogs", "catalog_item_nav"])
        self.assertFalse(effective_show_catalog_index_row(u, SLUG_CONTAINER_PASSPORT))

        prof.catalog_item_nav = {SLUG_CONTAINER_PASSPORT: UserAccessProfile.NavOverride.SHOW}
        prof.save(update_fields=["catalog_item_nav"])
        self.assertTrue(effective_show_catalog_index_row(u, SLUG_CONTAINER_PASSPORT))


class WasteDocAccessTests(TestCase):
    def test_admin_and_dispecer_see_all_waste_docs(self):
        u_admin = User.objects.create_user(username="t_admin", password="x")
        set_user_role(u_admin, ROLE_ADMIN)
        self.assertTrue(can_see_all_waste_docs(u_admin))

        u_disp = User.objects.create_user(username="t_disp", password="x")
        set_user_role(u_disp, ROLE_DISPECER)
        self.assertTrue(can_see_all_waste_docs(u_disp))

    def test_zadavatel_does_not_see_all_waste_docs(self):
        u = User.objects.create_user(username="t_zad", password="x")
        set_user_role(u, ROLE_ZADAVATEL)
        self.assertFalse(can_see_all_waste_docs(u))

    def test_anonymous_does_not_see_all(self):
        from types import SimpleNamespace

        self.assertFalse(can_see_all_waste_docs(SimpleNamespace(is_authenticated=False)))

    def test_only_admin_with_profile_flag_can_delete_all_pruvodky(self):
        admin = User.objects.create_user(username="t_admin_delete", password="x", is_superuser=True)
        set_user_role(admin, ROLE_ADMIN)
        self.assertFalse(can_delete_all_pruvodky(admin))
        profile = get_access_profile(admin)
        profile.can_delete_all_pruvodky = True
        profile.save(update_fields=["can_delete_all_pruvodky"])
        self.assertTrue(can_delete_all_pruvodky(admin))

        disp = User.objects.create_user(username="t_disp_delete", password="x")
        set_user_role(disp, ROLE_DISPECER)
        self.assertFalse(can_delete_all_pruvodky(disp))

    def test_dashboard_notes_permission_from_profile(self):
        u = User.objects.create_user(username="t_notes", password="x")
        set_user_role(u, ROLE_DISPECER)
        self.assertTrue(can_manage_dashboard_notes(u))
        prof = get_access_profile(u)
        prof.can_manage_dashboard_notes = False
        prof.save(update_fields=["can_manage_dashboard_notes"])
        self.assertFalse(can_manage_dashboard_notes(u))

    def test_superuser_always_can_manage_dashboard_notes(self):
        u = User.objects.create_user(username="t_notes_su", password="x", is_superuser=True)
        set_user_role(u, ROLE_ADMIN)
        prof = get_access_profile(u)
        prof.can_manage_dashboard_notes = False
        prof.save(update_fields=["can_manage_dashboard_notes"])
        self.assertTrue(can_manage_dashboard_notes(u))

    def test_global_role_matrix_controls_inherit_dashboard_nav(self):
        u = User.objects.create_user(username="t_nav_matrix", password="x")
        set_user_role(u, ROLE_DISPECER)
        prof = get_access_profile(u)
        prof.nav_dashboard = UserAccessProfile.NavOverride.INHERIT
        prof.save(update_fields=["nav_dashboard"])
        s = AppSettings.load()
        patch = {
            ROLE_DISPECER: {
                "dashboard": False,
                "pruvodky": True,
                "catalogs": True,
                "settings": False,
                "address_data": False,
            }
        }
        s.role_nav_defaults = patch
        s.save(update_fields=["role_nav_defaults"])
        self.assertFalse(effective_show_dashboard_nav(u))
        s.role_nav_defaults = {}
        s.save(update_fields=["role_nav_defaults"])
        self.assertTrue(effective_show_dashboard_nav(u))


class UserAdminPasswordTests(TestCase):
    def _minimal_profile_post_payload(self, target):
        ep = get_access_profile(target)
        from catalogs.catalog_nav_registry import catalog_index_rows

        out = {
            "can_edit_existing_pruvodka": ep.can_edit_existing_pruvodka,
            "can_create_pruvodka": ep.can_create_pruvodka,
            "can_delete_all_pruvodky": ep.can_delete_all_pruvodky,
            "can_manage_dashboard_notes": ep.can_manage_dashboard_notes,
            "sberny_dvur_subject": "",
            "export_pio_profile": ep.export_pio_profile,
            "nav_dashboard": ep.nav_dashboard,
            "nav_pruvodky": ep.nav_pruvodky,
            "nav_customer_requests": ep.nav_customer_requests,
            "nav_invoice_queue": ep.nav_invoice_queue,
            "nav_catalogs": ep.nav_catalogs,
            "nav_settings": ep.nav_settings,
            "nav_address_data": ep.nav_address_data,
            "nav_reports": ep.nav_reports,
        }
        for slug, _ in catalog_index_rows():
            raw = ep.catalog_item_nav or {}
            val = raw.get(slug, UserAccessProfile.NavOverride.INHERIT)
            out[f"catnav_{slug}"] = val
        return out

    def test_admin_edit_accepts_short_password_1973(self):
        admin = User.objects.create_user(username="pw_admin", password="adminpass")
        admin.is_superuser = True
        admin.save()
        target = User.objects.create_user(username="Morcova", password="oldpass")
        set_user_role(target, ROLE_ZADAVATEL)
        payload = {
            "username": "Morcova",
            "email": "",
            "role": ROLE_ZADAVATEL,
            "new_password1": "1973",
            "new_password2": "1973",
            **self._minimal_profile_post_payload(target),
        }
        form = UserAdminEditForm(data=payload, instance=target, editor=admin)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.check_password("1973"))

    def test_admin_edit_password_error_on_field_not_hidden(self):
        admin = User.objects.create_user(username="pw_admin2", password="adminpass")
        admin.is_superuser = True
        admin.save()
        target = User.objects.create_user(username="pw_target", password="oldpass")
        set_user_role(target, ROLE_ZADAVATEL)
        payload = {
            "username": "pw_target",
            "email": "",
            "role": ROLE_ZADAVATEL,
            "new_password1": "12",
            "new_password2": "12",
            **self._minimal_profile_post_payload(target),
        }
        form = UserAdminEditForm(data=payload, instance=target, editor=admin)
        self.assertFalse(form.is_valid())
        self.assertIn("new_password1", form.errors)


class UserSubjectToggleEditorVisibilityTests(TestCase):
    """Viditelnost oprávnění „Smí měnit“ u polí subjektu F/P při úpravě uživatele."""

    def test_superuser_sees_all_subject_toggle_fields(self):
        su = User.objects.create_user(username="su_subj", password="x", is_superuser=True)
        target = User.objects.create_user(username="tgt_subj", password="x")
        form = UserAdminEditForm(instance=target, editor=su)
        from users.forms.access_profile import SUBJECT_TOGGLE_PERMISSION_FIELDS

        for fname in SUBJECT_TOGGLE_PERMISSION_FIELDS:
            self.assertIn(fname, form.fields)

    def test_non_super_shows_only_own_subject_toggle_permissions(self):
        editor = User.objects.create_user(username="ed_subj", password="x")
        editor.is_superuser = False
        editor.save()
        ep = get_access_profile(editor)
        ep.can_toggle_subject_is_municipality = True
        ep.can_toggle_subject_collection_yard = False
        ep.can_toggle_subject_system_generates_zpo = False
        ep.save()

        target = User.objects.create_user(username="tgt_subj2", password="x")
        form = UserAdminEditForm(instance=target, editor=editor)

        self.assertIn("can_toggle_subject_is_municipality", form.fields)
        self.assertNotIn("can_toggle_subject_collection_yard", form.fields)
        self.assertNotIn("can_toggle_subject_system_generates_zpo", form.fields)

    def test_access_profile_defaults_preserves_hidden_subject_toggles_on_edit(self):
        editor = User.objects.create_user(username="ed_merge", password="x")
        editor.is_superuser = False
        editor.save()
        ep_ed = get_access_profile(editor)
        ep_ed.can_toggle_subject_is_municipality = True
        ep_ed.save()

        target = User.objects.create_user(username="tgt_merge", password="x")
        ep_tgt = get_access_profile(target)
        ep_tgt.can_toggle_subject_collection_yard = True
        ep_tgt.save()

        form = UserAdminEditForm(
            instance=target,
            editor=editor,
            data={
                "username": target.username,
                "email": "",
                "role": ROLE_ADMIN,
                "can_toggle_subject_is_municipality": True,
                **self._minimal_profile_post_payload(target),
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        merged = access_profile_defaults_for_save(form, existing_profile=ep_tgt)
        self.assertTrue(merged["can_toggle_subject_is_municipality"])
        self.assertTrue(
            merged["can_toggle_subject_collection_yard"],
            "Pole skryté editorovi se má zachovat z cílového profilu.",
        )

    def _minimal_profile_post_payload(self, target):
        """Výchozí POST pro zbývající pole přístupového profilu (bez subject toggles mimo formulář)."""
        ep = get_access_profile(target)
        from users.forms.access_profile import UserAccessProfileForm

        from catalogs.catalog_nav_registry import catalog_index_rows

        out = {
            "can_edit_existing_pruvodka": ep.can_edit_existing_pruvodka,
            "can_create_pruvodka": ep.can_create_pruvodka,
            "can_delete_all_pruvodky": ep.can_delete_all_pruvodky,
            "can_manage_dashboard_notes": ep.can_manage_dashboard_notes,
            "sberny_dvur_subject": "",
            "export_pio_profile": ep.export_pio_profile,
            "nav_dashboard": ep.nav_dashboard,
            "nav_pruvodky": ep.nav_pruvodky,
            "nav_customer_requests": ep.nav_customer_requests,
            "nav_invoice_queue": ep.nav_invoice_queue,
            "nav_catalogs": ep.nav_catalogs,
            "nav_settings": ep.nav_settings,
            "nav_address_data": ep.nav_address_data,
            "nav_reports": ep.nav_reports,
        }
        for slug, _ in catalog_index_rows():
            raw = ep.catalog_item_nav or {}
            val = raw.get(slug, UserAccessProfile.NavOverride.INHERIT)
            out[f"catnav_{slug}"] = val
        return out


class DashboardCreateRideIconTests(TestCase):
    def test_can_create_pruvodka_dashboard_roles(self):
        admin = User.objects.create_user(username="dash_cr_admin", password="x")
        set_user_role(admin, ROLE_ADMIN)
        self.assertTrue(can_create_pruvodka_dashboard(admin))

        disp = User.objects.create_user(username="dash_cr_disp", password="x")
        set_user_role(disp, ROLE_DISPECER)
        self.assertTrue(can_create_pruvodka_dashboard(disp))

        zad = User.objects.create_user(username="dash_cr_zad", password="x")
        set_user_role(zad, ROLE_ZADAVATEL)
        self.assertFalse(can_create_pruvodka_dashboard(zad))

    def test_can_create_pruvodka_respects_profile_flag(self):
        disp = User.objects.create_user(username="dash_cr_disp_off", password="x")
        set_user_role(disp, ROLE_DISPECER)
        prof = get_access_profile(disp)
        prof.can_create_pruvodka = False
        prof.save(update_fields=["can_create_pruvodka"])
        self.assertFalse(can_create_pruvodka(disp))
        self.assertFalse(can_create_pruvodka_dashboard(disp))

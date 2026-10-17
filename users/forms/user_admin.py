import copy

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from users.constants import ROLE_CHOICES, ROLE_RIDIC, ROLE_SBERNY_DVUR
from users.forms.access_profile import SUBJECT_TOGGLE_PERMISSION_FIELDS, UserAccessProfileForm
from users.models import UserAccessProfile
from users.services.roles import get_user_role_label

ADMIN_SET_PASSWORD_MIN_LENGTH = 4
ADMIN_PASSWORD_HELP_TEXT = (
    f"Minimálně {ADMIN_SET_PASSWORD_MIN_LENGTH} znaky. "
    "Administrátor může nastavit i jednoduché heslo (např. rok narození)."
)


def validate_admin_set_password(password: str) -> None:
    """Pravidla hesla při zakládání / úpravě uživatele administrátorem (ne self-service)."""
    if len(password) < ADMIN_SET_PASSWORD_MIN_LENGTH:
        raise forms.ValidationError(
            f"Heslo musí mít alespoň {ADMIN_SET_PASSWORD_MIN_LENGTH} znaky.",
            code="password_too_short",
        )


def filter_subject_toggle_fields_for_editor(form: forms.BaseForm, editor: User | None) -> None:
    """
    Superuser vidí všechna oprávnění „Smí měnit“ u polí subjektu F/P.

    Ostatní uživatelé vidí jen řádky, které mají sami povolené na svém přístupovém profilu.
    """
    if editor is None or getattr(editor, "is_superuser", False):
        return
    ep = UserAccessProfile.objects.filter(user_id=editor.pk).first()
    for fname in SUBJECT_TOGGLE_PERMISSION_FIELDS:
        if fname not in form.fields:
            continue
        if ep is None or not getattr(ep, fname, False):
            form.fields.pop(fname, None)


def access_profile_defaults_for_save(
    form: forms.BaseForm,
    *,
    existing_profile: UserAccessProfile | None = None,
) -> dict:
    """
    Hodnoty pro ``UserAccessProfile`` po uložení uživatelského formuláře.

    Pole „Smí měnit u subjektu F/P“, která editor neviděl (nemá oprávnění), se nepřepisují —
    zůstanou z ``existing_profile`` nebo výchozí z modelu.
    """
    defaults: dict = {}
    meta = UserAccessProfile._meta
    for k in UserAccessProfileForm.core_profile_keys():
        if k in form.cleaned_data:
            defaults[k] = form.cleaned_data[k]
            continue
        if k in SUBJECT_TOGGLE_PERMISSION_FIELDS:
            if existing_profile is not None:
                defaults[k] = getattr(existing_profile, k)
            else:
                defaults[k] = meta.get_field(k).get_default()
            continue
        raise AssertionError(f"Neočekávaně chybí klíč profilu ve formuláři: {k}")
    defaults["catalog_item_nav"] = UserAccessProfileForm.catalog_overrides_from_cleaned(form.cleaned_data)
    return defaults


class SubjectToggleSectionMixin:
    """Zobrazení bloku checkboxů oprávnění k úpravám polí subjektu F/P."""

    @property
    def show_subject_toggle_section(self) -> bool:
        return any(fname in self.fields for fname in SUBJECT_TOGGLE_PERMISSION_FIELDS)


def _attach_profile_fields(form: forms.BaseForm, user: User | None = None) -> None:
    profile = None
    if user and user.pk:
        profile = UserAccessProfile.objects.filter(user_id=user.pk).first()
    pform = UserAccessProfileForm(instance=profile)
    for name, field in pform.fields.items():
        form.fields[name] = copy.deepcopy(field)
    # ModelForm dává hodnoty z instance do pform.initial, ne vždy do field.initial — bez toho by se např.
    # „Smí upravovat existující průvodky“ a subjekt sběrného dvora v editaci uživatele nezobrazily.
    if getattr(pform, "initial", None):
        for key, val in pform.initial.items():
            if key in form.fields:
                form.initial[key] = val


class UserWithRoleCreationForm(SubjectToggleSectionMixin, UserCreationForm):
    role = forms.ChoiceField(label="Role", choices=ROLE_CHOICES)
    email = forms.EmailField(label="E-mail", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")

    def __init__(self, *args, editor=None, **kwargs):
        self.editor = editor
        super().__init__(*args, **kwargs)
        _attach_profile_fields(self, None)
        filter_subject_toggle_fields_for_editor(self, editor)
        if "password1" in self.fields:
            self.fields["password1"].help_text = ADMIN_PASSWORD_HELP_TEXT

    def validate_password_for_user(self, user, password_field_name="password2"):
        password = self.cleaned_data.get(password_field_name)
        if password:
            try:
                validate_admin_set_password(password)
            except forms.ValidationError as exc:
                self.add_error(password_field_name, exc)

    def clean(self):
        data = super().clean()
        role = (data.get("role") or "").strip()
        if role != ROLE_RIDIC:
            data["driver_profile"] = None
        if role == ROLE_SBERNY_DVUR and not data.get("sberny_dvur_subject"):
            raise forms.ValidationError(
                'U role „Sběrný dvůr“ vyberte subjekt sběrného dvora (číselník F/P osoby).'
            )
        if role == ROLE_SBERNY_DVUR and data.get("sberny_dvur_subject"):
            subj = data["sberny_dvur_subject"]
            if not getattr(subj, "is_collection_yard", False):
                raise forms.ValidationError(
                    "Vybraný subjekt nemá v číselníku zapnuté „Lokalita sběrného dvora“ — upravte záznam F/P."
                )
        return data


class UserAdminEditForm(SubjectToggleSectionMixin, forms.ModelForm):
    """Úprava uživatele: údaje, role, přístupový profil a volitelně nové heslo."""

    role = forms.ChoiceField(label="Role", choices=ROLE_CHOICES)
    new_password1 = forms.CharField(
        label="Nové heslo",
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        required=False,
        help_text="Ponechte prázdné, pokud heslo neměníte. " + ADMIN_PASSWORD_HELP_TEXT,
    )
    new_password2 = forms.CharField(
        label="Potvrzení hesla",
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        required=False,
    )

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, editor=None, **kwargs):
        self.editor = editor
        super().__init__(*args, **kwargs)
        _attach_profile_fields(self, self.instance if self.instance else None)
        filter_subject_toggle_fields_for_editor(self, editor)
        if self.instance and self.instance.pk:
            current = get_user_role_label(self.instance)
            if current != "-":
                self.fields["role"].initial = current

    def clean_username(self):
        raw = self.cleaned_data.get("username")
        username = (raw or "").strip()
        if not username:
            raise forms.ValidationError("Zadejte přihlašovací jméno.")
        conflict = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            conflict = conflict.exclude(pk=self.instance.pk)
        if conflict.exists():
            raise forms.ValidationError(
                "Toto přihlašovací jméno již v databázi existuje. Zvolte jiné.",
                code="username_exists",
            )
        return username

    def clean(self):
        data = super().clean()
        p1 = (data.get("new_password1") or "").strip()
        p2 = (data.get("new_password2") or "").strip()
        if p1 or p2:
            if p1 != p2:
                self.add_error("new_password2", "Hesla se neshodují.")
            else:
                try:
                    validate_admin_set_password(p1)
                except forms.ValidationError as exc:
                    self.add_error("new_password1", exc)
                else:
                    data["new_password1"] = p1
                    data["new_password2"] = p2
        role = (data.get("role") or "").strip()
        if role != ROLE_RIDIC:
            data["driver_profile"] = None
        if role == ROLE_SBERNY_DVUR and not data.get("sberny_dvur_subject"):
            raise forms.ValidationError(
                'U role „Sběrný dvůr“ vyberte subjekt sběrného dvora (číselník F/P osoby).'
            )
        if role == ROLE_SBERNY_DVUR and data.get("sberny_dvur_subject"):
            subj = data["sberny_dvur_subject"]
            if not getattr(subj, "is_collection_yard", False):
                raise forms.ValidationError(
                    "Vybraný subjekt nemá v číselníku zapnuté „Lokalita sběrného dvora“ — upravte záznam F/P."
                )
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = (self.cleaned_data.get("new_password1") or "").strip()
        if pw:
            user.set_password(pw)
        if commit:
            user.save()
        return user

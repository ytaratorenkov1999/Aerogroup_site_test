from typing import Any

from django import forms
from unfold.widgets import UnfoldAdminPasswordWidget

from .models import MonitoringAgent


class MonitoringAgentForm(forms.ModelForm):
    api_token = forms.CharField(
        label="Новый токен", required=False,
        min_length=32, max_length=256, strip=False,
        widget=UnfoldAdminPasswordWidget(
            attrs={
                "autocomplete": "new-password",
                "spellcheck": "false",
                "placeholder": "Вставьте новый токен агента",
            },
            render_value=False,
        ),
        help_text="Пустое поле сохраняет текущий токен. Исходный токен не хранится.",
    )

    class Meta:
        model = MonitoringAgent
        fields = ("server", "site_id", "agent_id", "enabled")

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        token = cleaned.get("api_token")
        if token:
            try:
                self.instance.set_api_token(token)
                existing = MonitoringAgent.objects.filter(
                    token_hash=self.instance.token_hash
                ).exclude(pk=self.instance.pk)
                if existing.exists():
                    self.add_error("api_token", "Этот токен уже используется.")
            except forms.ValidationError as error:
                self.add_error("api_token", error)
        return cleaned

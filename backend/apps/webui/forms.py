from django import forms

from apps.tenants.models import Property, Tenant
from apps.workers.models import Area, Shift, SpecialState, Worker


class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = [
            "name",
            "active",
        ]


class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = [
            "document_number",
            "first_name",
            "last_name",
            "area",
            "active",
        ]


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = [
            "area",
            "name",
            "buk_code",
            "start_time",
            "end_time",
            "break_start",
            "break_end",
            "is_night_shift",
            "active",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "break_start": forms.TimeInput(attrs={"type": "time"}),
            "break_end": forms.TimeInput(attrs={"type": "time"}),
        }


class SpecialStateForm(forms.ModelForm):
    class Meta:
        model = SpecialState
        fields = [
            "name",
            "buk_code",
            "active",
        ]


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "name",
            "slug",
            "location",
            "status",
        ]


class TenantForm(forms.ModelForm):
    settings = forms.JSONField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = Tenant
        fields = [
            "name",
            "slug",
            "status",
            "settings",
        ]

from django import forms

from .models import VolunteerApplication


class VolunteerApplicationForm(forms.ModelForm):
    class Meta:
        model = VolunteerApplication
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "city",
            "birth_date",
            "interested_area",
            "motivation",
            "health_declaration",
            "kvkk_consent",
            "health_data_consent",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "motivation": forms.Textarea(attrs={"rows": 4}),
            "health_declaration": forms.Textarea(attrs={"rows": 3}),
        }

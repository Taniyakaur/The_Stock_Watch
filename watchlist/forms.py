from django import forms
from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True, help_text="Target-price alerts are emailed here."
    )

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

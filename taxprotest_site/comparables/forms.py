from __future__ import annotations

from django import forms


class PropertySearchForm(forms.Form):
    acct = forms.CharField(
        label="Tax Account Number", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors', 'placeholder': 'Tax Account Number'})
    )
    owner = forms.CharField(
        label="Owner Name", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors', 'placeholder': 'Owner Name'})
    )
    street = forms.CharField(
        label="Street Name", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors', 'placeholder': 'Street Name'})
    )
    zip_code = forms.CharField(
        label="Zip Code", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors', 'placeholder': 'Zip Code'})
    )
    exact_match = forms.BooleanField(
        label="Exact street name match", 
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 bg-gray-100 border-gray-300 rounded focus:ring-primary-500 focus:ring-2'})
    )
    page_size = forms.ChoiceField(
        label="Page Size",
        choices=[(str(n), str(n)) for n in (25, 50, 100, 200)],
        initial="50",
        required=False,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors bg-white'})
    )


class ComparablesParamForm(forms.Form):
    max = forms.IntegerField(label="Max Comparables", initial=25, min_value=1, required=False)
    min = forms.IntegerField(label="Min Comparables", initial=20, min_value=1, required=False)
    max_radius = forms.FloatField(label="Max Radius (miles)", required=False)
    strict_first = forms.BooleanField(label="Strict Radius First", required=False, initial=False)

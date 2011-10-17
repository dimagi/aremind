import random
import string
import datetime
import re

from django.conf import settings
from django import forms
from django.forms.models import modelformset_factory

from rapidsms.models import Contact
from selectable.forms import AutoComboboxSelectMultipleField

from aremind.apps.adherence.models import QuerySchedule
from aremind.apps.adherence.types import *
from aremind.apps.adherence.lookups import ReminderLookup, FeedLookup, QueryLookup
from aremind.apps.groups.forms import FancyPhoneInput
from aremind.apps.groups.validators import validate_phone, validate_unique_phone
from aremind.apps.groups.utils import normalize_number
from aremind.apps.patients import models as patients


XML_DATE_FORMATS = ('%b  %d %Y ',)
XML_TIME_FORMATS = ('%H:%M', )

_ = lambda s: s

class PatientForm(forms.ModelForm):
    # NB: This form is only used for importing patient data
    # The PatientRemindersForm is used in the UI
    date_enrolled = forms.DateField(input_formats=XML_DATE_FORMATS)
    next_visit = forms.DateField(input_formats=XML_DATE_FORMATS,
                                 required=False)
    reminder_time = forms.TimeField(input_formats=XML_TIME_FORMATS,
                                    required=False)

    class Meta(object):
        model = patients.Patient
        exclude = ('raw_data', 'contact', 'batterystrength')

    def clean_mobile_number(self):
        mobile_number = normalize_number(self.cleaned_data['mobile_number'])
        validate_phone(mobile_number)
        return mobile_number

    def save(self, payload):
        instance = super(PatientForm, self).save(commit=False)
        instance.raw_data = payload
        instance.raw_data.status = 'success'
        instance.raw_data.save()
        # get or create associated contact record
        if not instance.contact_id:
            subject_number = instance.subject_number
            contact, _ = Contact.objects.get_or_create(name=subject_number)
            instance.contact = contact
        instance.contact.phone = instance.mobile_number
        instance.contact.pin = instance.pin
        instance.contact.save()
        instance.save()
        return instance


class PatientPayloadUploadForm(forms.ModelForm):
    data_file = forms.FileField(required=False)

    class Meta(object):
        model = patients.PatientDataPayload
        fields = ('raw_data', )

    def __init__(self, *args, **kwargs):
        super(PatientPayloadUploadForm, self).__init__(*args, **kwargs)
        self.fields['raw_data'].required = False

    def clean(self):
        raw_data = self.cleaned_data.get('raw_data', '')
        data_file = self.cleaned_data.get('data_file', None)
        if not (raw_data or data_file):
            raise forms.ValidationError('You must either upload a file or include raw data.')
        if data_file and not raw_data:
            self.cleaned_data['raw_data'] = data_file.read()
        return self.cleaned_data


class PatientRemindersForm(forms.ModelForm):

    password = forms.CharField(max_length=20, required=True)
    language = forms.ChoiceField(choices=getattr(settings, "LANGUAGES"), required=True)
    survey_active = forms.BooleanField(required=False)
    mobile_network = forms.CharField(max_length=50, required=False)

    class Meta(object):
        model = patients.Patient
        fields = ('subject_number', 'mobile_number', 'reminder_time', 'password', 'language', 'survey_active', 'mobile_network')

    def __init__(self, *args, **kwargs):
        super(PatientRemindersForm, self).__init__(*args, **kwargs)
        self.fields['mobile_number'].widget = FancyPhoneInput()
        self.fields['reminder_time'].widget.attrs.update({'class': 'timepicker'})
        self.fields['reminder_time'].label = 'Daily Survey Time'
        self.fields['reminder_time'].required = True
        if not (self.instance and self.instance.pk):
            self.initial['subject_number'] = self.generate_new_subject_id()
        if self.instance:
            if self.instance.contact_id:
                self.initial["language"] = self.instance.contact.language
                self.initial["password"] = self.instance.contact.password
                self.initial["mobile_network"] = self.instance.contact.mobile_network
            if self.instance.pk and self.instance.adherence_query_schedules.count() > 0:
                self.initial["survey_active"] = self.instance.adherence_query_schedules.all()[0].active
            else:
                self.initial["survey_active"] = True
                self.fields["survey_active"].widget.attrs["disabled"] = "disabled"

    """
    UW Kenya Implementation
    
    Added this function to validate that no whitespace characters are entered in the password field.
    """
    def clean_password(self):
        password = self.cleaned_data["password"]
        if(re.match(r"^.*\s.*$", password)):
            raise forms.ValidationError(_("The password cannot contain any spaces."))
        return password

    """
    UW Kenya Implementation
    
    Modified this function to also ensure uniqueness of mobile number.
    """
    def clean_mobile_number(self):
        mobile_number = normalize_number(self.cleaned_data['mobile_number'])
        validate_phone(mobile_number)
        if self.instance.contact_id:
            validate_unique_phone(mobile_number, self.instance.contact_id)
        else:
            validate_unique_phone(mobile_number, None)
        return mobile_number

    def clean_manual_adherence(self):
        return self.cleaned_data.get('manual_adherence', 0) or 0

    def generate_new_subject_id(self):
        valid = False
        while not valid:
            start = ''.join([random.choice(string.digits) for i in range(3)])
            end = ''.join([random.choice(string.digits) for i in range(5)])
            test = '%s-%s' % (start, end)
            valid = not patients.Patient.objects.filter(subject_number=test).exists()
        return test

    def generate_new_pin(self):
        return ''.join([random.choice(string.digits) for i in range(4)])
         
    """
    UW Implementation
    
    In this implementation of ARemind, each patient has a single query schedule,
    and each query schedule only belongs to one patient. When a patient is added,
    a query schedule is automatically created for them.
    """
    def save(self, *args, **kwargs):
        patient = super(PatientRemindersForm, self).save(commit=False)
        
        #Save contact information for patient
        if not patient.contact_id:
            contact, _ = Contact.objects.get_or_create(name=patient.subject_number)
            patient.contact = contact
        patient.contact.phone = patient.mobile_number
        patient.contact.password = self.cleaned_data["password"]
        patient.contact.language = self.cleaned_data["language"]
        patient.contact.mobile_network = self.cleaned_data["mobile_network"]
        patient.contact.save()
        patient.save()
        
        #Create QuerySchedule for the patient if necessary
        if patient.adherence_query_schedules.count() == 0:
            query_schedule = QuerySchedule(
                start_date = patient.date_enrolled + datetime.timedelta(days=1)
               ,time_of_day = patient.reminder_time
               ,query_type = QUERY_TYPE_SMS
               ,last_run = None
               ,active = True
               ,days_between = 1
            )
            query_schedule.save()
            query_schedule.patients.add(patient)
        else:
            query_schedule = patient.adherence_query_schedules.all()[0]
            query_schedule.time_of_day = patient.reminder_time
            query_schedule.active = self.cleaned_data["survey_active"]
            query_schedule.save()
        
        return patient


class PatientOnetimeMessageForm(forms.Form):
    message = forms.CharField(label="Message", max_length=140, min_length=1, 
                              widget=forms.Textarea)


class PillHistoryForm(forms.ModelForm):
    
    class Meta(object):
        model = patients.PatientPillsTaken
        fields = ('date', 'num_pills', )

    def __init__(self, *args, **kwargs):
        super(PillHistoryForm, self).__init__(*args, **kwargs)
        self.fields['date'].widget.attrs.update({'class': 'datepicker'})

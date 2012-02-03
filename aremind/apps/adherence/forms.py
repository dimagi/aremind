from django import forms

from rapidsms.models import Contact

from aremind.apps.adherence.models import Reminder, Feed, Entry, QuerySchedule
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _


class ReminderForm(forms.ModelForm):

    weekdays = forms.MultipleChoiceField(choices=Reminder.WEEKDAY_CHOICES, widget=forms.CheckboxSelectMultiple)
    message = forms.CharField(label="Message", max_length=160, widget=forms.Textarea)

    class Meta(object):
        model = Reminder
        fields = ('frequency', 'weekdays', 'time_of_day', 'end_date', 'message', 'recipients', )

    def __init__(self, *args, **kwargs):
        super(ReminderForm, self).__init__(*args, **kwargs)
        self.fields['time_of_day'].widget.attrs.update({'class': 'timepicker'})

        self.fields['recipients'].widget.attrs.update({'class': 'multiselect'})
        self.fields['recipients'].help_text = u''       
        qs = Contact.objects.filter(patient__isnull=False).order_by('patient__subject_number')
        self.fields['recipients'].queryset = qs
        self.fields['recipients'].label_from_instance = self.label_from_instance
        self.fields['end_date'].widget.attrs.update({'class': 'datepicker'})

    def label_from_instance(self, obj):
        return obj.patient_set.all()[0].subject_number

    def clean_weekdays(self):
        weekdays = self.cleaned_data.get('weekdays', [])
        return u','.join(weekdays)

    def clean(self):
        super(ReminderForm, self).clean()
        frequency = self.cleaned_data.get('frequency', None)
        if frequency and frequency == Reminder.REPEAT_DAILY:
            self.cleaned_data['weekdays'] = None
            if 'weekdays' in self._errors:
                del self._errors['weekdays']
        return self.cleaned_data


class FeedForm(forms.ModelForm):

    class Meta(object):
        model = Feed
        fields = ('name', 'feed_type', 'url', 'description', 'subscribers', 'active', )
    
    def __init__(self, *args, **kwargs):
        super(FeedForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget = forms.Textarea()
        self.fields['subscribers'].widget.attrs.update({'class': 'multiselect'})
        self.fields['subscribers'].help_text = u''       
        qs = Contact.objects.filter(patient__isnull=False).order_by('patient__subject_number')
        self.fields['subscribers'].queryset = qs
        self.fields['subscribers'].label_from_instance = self.label_from_instance

    def label_from_instance(self, obj):
        return obj.patient_set.all()[0].subject_number

    def clean(self):
        super(FeedForm,self).clean()
        if self.is_valid(): #  so far, anyway
            self.instance.name = self.cleaned_data['name']
            self.instance.feed_type = self.cleaned_data['feed_type']
            if not self.instance.is_valid_feed():
                raise ValidationError("Not a valid feed")
        return self.cleaned_data

class EntryForm(forms.ModelForm):

    percent_max = forms.IntegerField(
        required=False, max_value=100, min_value=0,
        help_text="The max adherence percentage to be shown this message."
    )
    percent_min = forms.IntegerField(
        required=False, max_value=100, min_value=0,
        help_text="The min adherence percentage to be shown this message."
    )

    class Meta(object):
        model = Entry
        fields = ('content', 'published', 'percent_max', 'percent_min', )

    def __init__(self, *args, **kwargs):
        super(EntryForm, self).__init__(*args, **kwargs)
        self.fields['published'].widget.attrs.update({'class': 'datetimepicker'})
        if self.instance and self.instance.feed:
            feed = self.instance.feed
            if feed.feed_type != Feed.TYPE_MANUAL:
                # Drop percentage fields
                del self.fields['percent_max']
                del self.fields['percent_min']
            else:
                # Add help text for manual entries
                self.fields['content'].help_text = ("Enter a message for the patient. " + 
                "You message can include the patient's current adherence percentage as {{ adherence }} or " +
                "the number of days to get back to 95% adherence as {{ days }}.")

    def clean(self):
        super(EntryForm, self).clean()
        if self.instance and self.instance.feed:
            feed = self.instance.feed
            if feed.feed_type != Feed.TYPE_MANUAL:
                self.cleaned_data['percent_max'] = None 
                self.cleaned_data['percent_min'] = None
        percent_max = self.cleaned_data.get('percent_max', None)
        percent_min = self.cleaned_data.get('percent_min', None)
        if percent_max and percent_min and percent_min > percent_max:
            raise forms.ValidationError('Max adherence percentage much be greater than min.')
        return self.cleaned_data
            

class QueryScheduleForm(forms.ModelForm):
    class Meta(object):
        model = QuerySchedule
        exclude = ('recipients',)

    def __init__(self, *args, **kwargs):
        super(QueryScheduleForm, self).__init__(*args, **kwargs)
        remove_message = unicode(_('Hold down "Control", or "Command" on a Mac, to select more than one.'))
        self.fields['start_date'].label = 'Start date'
        self.fields['start_date'].required = True
        self.fields['start_date'].widget.attrs['class'] = 'datepicker'
        self.fields['time_of_day'].widget.attrs['class'] = 'timepicker'
        self.fields['patients'].widget.attrs['class'] = 'multiselect'
        self.fields['patients'].help_text = self.fields['patients'].help_text.replace(remove_message, '').strip()

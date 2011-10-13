# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        #This view shows all decisiontree_entry records joined to their corresponding decisiontree_treestate.
        
        db.execute("""
            CREATE OR REPLACE VIEW decisiontree_entry_treestate AS
            SELECT  A.session_id
                   ,A.text
                   ,C.name
            FROM    decisiontree_entry A
            JOIN    decisiontree_transition B   ON  A.transition_id = B.id
            JOIN    decisiontree_treestate C    ON  B.current_state_id = C.id
        """)
        
        #This view "flattens" the data from view decisiontree_entry_treestate to produce one record per UW Kenya survey.
        
        db.execute("""
            CREATE OR REPLACE VIEW adherence_uwkenyasurvey AS
            SELECT          A.id AS session_id
                           ,A.start_date
                           ,D.subject_number
                           ,C.phone
                           ,C.language
                           ,C.mobile_network
                           ,K.text AS ask_password_response
                           ,E.text AS daily_question1_response
                           ,F.text AS daily_question2_response
                           ,G.text AS daily_question3_response
                           ,H.text AS daily_question4_response
                           ,I.text AS monthly_question1_response
                           ,J.text AS monthly_question2_response
            FROM            decisiontree_session A
            JOIN            rapidsms_connection B                   ON  A.connection_id = B.id
            JOIN            rapidsms_contact C                      ON  B.contact_id = C.id
            JOIN            patients_patient D                      ON  C.id = D.contact_id
            LEFT OUTER JOIN decisiontree_entry_treestate E          ON  A.id = E.session_id AND E.name = 'ask_daily_question1'
            LEFT OUTER JOIN decisiontree_entry_treestate F          ON  A.id = F.session_id AND F.name = 'ask_daily_question2'
            LEFT OUTER JOIN decisiontree_entry_treestate G          ON  A.id = G.session_id AND G.name = 'ask_daily_question3'
            LEFT OUTER JOIN decisiontree_entry_treestate H          ON  A.id = H.session_id AND H.name = 'ask_daily_question4'
            LEFT OUTER JOIN decisiontree_entry_treestate I          ON  A.id = I.session_id AND I.name = 'ask_monthly_question1'
            LEFT OUTER JOIN decisiontree_entry_treestate J          ON  A.id = J.session_id AND J.name = 'ask_monthly_question2'
            LEFT OUTER JOIN decisiontree_entry_treestate K          ON  A.id = K.session_id AND K.name = 'ask_password'
        """)


    def backwards(self, orm):
        
        # Drop views
        
        db.execute("DROP VIEW IF EXISTS decisiontree_entry_treestate")
        db.execute("DROP VIEW IF EXISTS adherence_uwkenyasurvey")
    
    
    models = {
        'adherence.entry': {
            'Meta': {'ordering': "('-published',)", 'unique_together': "(('feed', 'uid'),)", 'object_name': 'Entry'},
            'added': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now_add': 'True', 'blank': 'True'}),
            'content': ('django.db.models.fields.TextField', [], {}),
            'feed': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'entries'", 'to': "orm['adherence.Feed']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'percent_max': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'percent_min': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'published': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'uid': ('django.db.models.fields.CharField', [], {'default': "'e9e9f2ed4179492e8624fe3453f4da36'", 'max_length': '255'})
        },
        'adherence.entryseen': {
            'Meta': {'unique_together': "(('entry', 'patient'),)", 'object_name': 'EntrySeen'},
            'entry': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['adherence.Entry']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'patient': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'entries_seen'", 'to': "orm['patients.Patient']"})
        },
        'adherence.feed': {
            'Meta': {'object_name': 'Feed'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'feed_type': ('django.db.models.fields.CharField', [], {'default': "'manual'", 'max_length': '20'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_download': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'subscribers': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'feeds'", 'blank': 'True', 'to': "orm['rapidsms.Contact']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        'adherence.patientsurvey': {
            'Meta': {'object_name': 'PatientSurvey'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_test': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'patient': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'surveys'", 'to': "orm['patients.Patient']"}),
            'query_type': ('django.db.models.fields.IntegerField', [], {}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '-2'})
        },
        'adherence.pillsmissed': {
            'Meta': {'object_name': 'PillsMissed'},
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'num_missed': ('django.db.models.fields.IntegerField', [], {}),
            'patient': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['patients.Patient']"}),
            'source': ('django.db.models.fields.IntegerField', [], {})
        },
        'adherence.queryschedule': {
            'Meta': {'object_name': 'QuerySchedule'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'days_between': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_run': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'patients': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'adherence_query_schedules'", 'symmetrical': 'False', 'to': "orm['patients.Patient']"}),
            'query_type': ('django.db.models.fields.IntegerField', [], {}),
            'recipients': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'adherence_query_schedules'", 'symmetrical': 'False', 'to': "orm['groups.Group']"}),
            'start_date': ('django.db.models.fields.DateField', [], {}),
            'time_of_day': ('django.db.models.fields.TimeField', [], {})
        },
        'adherence.reminder': {
            'Meta': {'object_name': 'Reminder'},
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'date_last_notified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'frequency': ('django.db.models.fields.CharField', [], {'default': "'daily'", 'max_length': '16', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'recipients': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'reminders'", 'blank': 'True', 'to': "orm['rapidsms.Contact']"}),
            'time_of_day': ('django.db.models.fields.TimeField', [], {}),
            'weekdays': ('django.db.models.fields.CommaSeparatedIntegerField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'})
        },
        'adherence.sendreminder': {
            'Meta': {'object_name': 'SendReminder'},
            'date_queued': ('django.db.models.fields.DateTimeField', [], {}),
            'date_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_to_send': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'recipient': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'adherence_reminders'", 'to': "orm['rapidsms.Contact']"}),
            'reminder': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'adherence_reminders'", 'to': "orm['adherence.Reminder']"}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'queued'", 'max_length': '20'})
        },
        'adherence.uwkenyasurvey': {
            'Meta': {'object_name': 'UWKenyaSurvey', 'managed': 'False'},
            'session_id': ('django.db.models.fields.IntegerField', [], {}),
            'start_date': ('django.db.models.fields.DateTimeField', [], {}),
            'subject_number': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '6', 'null': 'True', 'blank': 'True'}),
            'mobile_network': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'ask_password_response': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'daily_question1_response': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'daily_question2_response': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'daily_question3_response': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'daily_question4_response': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'monthly_question1_response': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'}),
            'monthly_question2_response': ('django.db.models.fields.CharField', [], {'max_length': '160', 'null': 'True', 'blank': 'True'})
        },
        'groups.group': {
            'Meta': {'object_name': 'Group'},
            'contacts': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'groups'", 'blank': 'True', 'to': "orm['rapidsms.Contact']"}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_editable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'})
        },
        'patients.patient': {
            'Meta': {'object_name': 'Patient'},
            'batterystrength': ('django.db.models.fields.IntegerField', [], {'default': '-1'}),
            'contact': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['rapidsms.Contact']", 'unique': 'True'}),
            'daily_doses': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'date_enrolled': ('django.db.models.fields.DateField', [], {'default': 'datetime.date(2011, 8, 11)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'manual_adherence': ('django.db.models.fields.IntegerField', [], {'default': '0', 'blank': 'True'}),
            'mobile_number': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'next_visit': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'pin': ('django.db.models.fields.CharField', [], {'max_length': '4', 'blank': 'True'}),
            'raw_data': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'patients'", 'null': 'True', 'to': "orm['patients.PatientDataPayload']"}),
            'reminder_time': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'subject_number': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '20'}),
            'wisepill_msisdn': ('django.db.models.fields.CharField', [], {'max_length': '12', 'blank': 'True'})
        },
        'patients.patientdatapayload': {
            'Meta': {'object_name': 'PatientDataPayload'},
            'error_message': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'raw_data': ('django.db.models.fields.TextField', [], {}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'received'", 'max_length': '16'}),
            'submit_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'rapidsms.backend': {
            'Meta': {'object_name': 'Backend'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '20'})
        },
        'rapidsms.contact': {
            'Meta': {'object_name': 'Contact'},
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '6', 'blank': 'True'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'pin': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'primary_backend': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'contact_primary'", 'null': 'True', 'to': "orm['rapidsms.Backend']"}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'})
        }
    }

    complete_apps = ['adherence']

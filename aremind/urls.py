from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
from django.views.generic.simple import direct_to_template


admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^my-project/', include('my_project.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    (r'^admin/', include(admin.site.urls)),
    (r'^', include('decisiontree.urls')),
#    (r'^', include('auditcare.urls')),

    # RapidSMS core URLs
    (r'^account/', include('rapidsms.urls.login_logout')),
    url(r'^$', 'aremind.apps.broadcast.views.dashboard', name='rapidsms-dashboard'),

    url(r'^settings/$', direct_to_template,
        {'template': 'aremind/not_implemented.html'}, name='settings'),

    # RapidSMS contrib app URLs
    (r'^ajax/', include('rapidsms.contrib.ajax.urls')),
    (r'^export/', include('rapidsms.contrib.export.urls')),
    url(r'^httptester/$',
        'threadless_router.backends.httptester.views.generate_identity',
        {'backend_name': 'httptester'}, name='httptester-index'),
    (r'^httptester/', include('threadless_router.backends.httptester.urls')),
    (r'^locations/', include('rapidsms.contrib.locations.urls')),
    (r'^messagelog/', include('rapidsms.contrib.messagelog.urls')),
    (r'^messaging/', include('rapidsms.contrib.messaging.urls')),
    (r'^registration/', include('rapidsms.contrib.registration.urls')),
#    (r'^scheduler/', include('rapidsms.contrib.scheduler.urls')),
    (r'^broadcast/', include('aremind.apps.broadcast.urls')),
    (r'^adherence/', include('aremind.apps.adherence.urls')),
    (r'^appointments/', include('aremind.apps.reminders.urls')),
    (r'^patients/', include('aremind.apps.patients.urls')),
    (r'^wisepill/', include('aremind.apps.wisepill.urls')),
    (r'^test-messager/', include('aremind.apps.test_messager.urls')),
    (r'^crm/', include('aremind.apps.groups.urls')),
    (r'^rosetta/', include('rosetta.urls')),
    (r'^selectable/', include('selectable.urls')),

    url(r'^tropo/$', 'rtropo.views.message_received', name = 'tropo', kwargs = { 'backend_name': 'tropo'} ),

#    (r'^couchlog/', include('couchlog.urls')),
)

 # Contrib Auth Password Management
urlpatterns += patterns('django.contrib.auth.views',   
    url(r'^account/password/change/$', 'password_change', name='auth_password_change'),
    url(r'^account/password/change/done/$', 'password_change_done', name='auth_password_change_done'),
    url(r'^account/password/reset/$', 'password_reset', name='auth_password_reset'),
    url(r'^account/password/reset/confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$', 'password_reset_confirm', 
        name='auth_password_reset_confirm'),
    url(r'^account/password/reset/complete/$', 'password_reset_complete', name='auth_password_reset_complete'),
    url(r'^account/password/reset/done/$', 'password_reset_done', name='auth_password_reset_done'),
)

if 'auditcare' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        (r'^', include('auditcare.urls')),
    )

if 'couchlog' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        (r'^couchlog/', include('couchlog.urls')),
    )

if settings.DEBUG:
    urlpatterns += patterns('',
        # helper URLs file that automatically serves the 'static' folder in
        # INSTALLED_APPS via the Django static media server (NOT for use in
        # production)
        (r'^', include('rapidsms.urls.static_media')),
        (r'^%s(?P<path>.*)' % settings.MEDIA_URL.lstrip('/'),
         'django.views.static.serve',
         {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}
        )
    )

    # For testing
    urlpatterns += patterns('',
        # ...
        url(r'^httptester/$',
            'threadless_router.backends.httptester.views.generate_identity',
            {'backend_name': 'httptester'}, name='httptester-index'),
        (r'^httptester/', include('threadless_router.backends.httptester.urls')),
        # ...
    )


ARemind
=======


The RapidSMS ARemind project...

Development Workflow
====================

We are using git-flow to help manage our development process.

Learn how to use git-flow at:
  http://jeffkreeftmeijer.com/2010/why-arent-you-using-git-flow/

You can download and install git-flow from:
  https://github.com/nvie/gitflow

Learn more about the methodology behind it at:
  http://nvie.com/posts/a-successful-git-branching-model/

Developer Setup
===============

**Prerequisites:**

* A Linux-based development environment including Python 2.6.  Ubuntu 10.04 or
  later is recommended.  At present, Windows-based environments are not
  actively supported.

* PostgreSQL and the appropriate Python bindings (``psycopg2``).  In
  Debian-based distributions, you can install these using ``apt-get``, e.g.::

    sudo apt-get install postgresql python-psycopg2 libpq-dev

* RabbitMQ::

    sudo apt-get install rabbitmq-server

* The following additional build dependencies::

    sudo apt-get install libxslt1-dev libxml2-dev mercurial python-setuptools python-dev libevent-dev

* CouchDB is required for logging and audit tracking purposes::

    sudo apt-get install couchdb

See
  http://wiki.apache.org/couchdb/Installing_on_Ubuntu
for more information about couch.



* Install pip and virtualenv, and make sure virtualenv is up to date, e.g.::

    sudo easy_install pip
    sudo pip install -U virtualenv
    sudo pip install -U virtualenvwrapper

* Once virtualenv and virtualenvwrapper are installed, add this command to your .bashrc file and then restart your terminal session: /usr/local/bin/virtualenvwrapper.sh

* If not done yet, install git and setup private/public keys (see http://help.github.com/linux-set-up-git/)

* Install git-flow (see above).

**To setup a local development environment, follow these steps:**

#. Clone the code from git, checkout the ``develop`` branch, and initialize
   git-flow::

    git clone git@github.com:dimagi/aremind.git
    cd aremind
    git checkout develop
    git checkout master
    git flow init # just accept all the default answers
  
#. Create a Python virtual environment for this project::

    mkvirtualenv --distribute aremind-dev
    workon aremind-dev

#. Install the project dependencies into the virtual environment::

    ./bootstrap.py

#. Create local settings file and initialize a development database::

    # ensure that database service is started if not already: (for example, sudo /etc/init.d/postgresql-8.4 start)
    cp localsettings.py.example localsettings.py
    createdb aremind_devel
    ./manage.py syncdb
    ./manage.py migrate

#. Update the submodules::

    git submodule init
    git submodule update


#. In one terminal, start RapidSMS router::

    mkdir logs
    ./manage.py runrouter

#. In another terminal, start the Django development server::

    ./manage.py runserver

#. In separate terminals, start celery and celerybeat:

    ./manage.py celeryd
    ./manage.py celerybeat

#. Open http://localhost:8000 in your web browser and you should see an
   **Installation Successful!** screen.



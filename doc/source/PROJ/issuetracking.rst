Issue Tracking
==============

`Redmine.dataone.org <https://redmine.datoane.org/>`_ is the primary issue
tracker used by the DatONE project. Some other components used by DataONE are
maintained elsewhere and use different issue trackers, including:

=============== ============= 
Product         Tracker
=============== =============
Infrastructure  `redmine.dataone.org/projects/d1 <https://redmine.dataone.org/projects/d1>`_
Member Nodes    `redmine.dataone.org/projects/mns <https://redmine.dataone.org/projects/mns>`_
www.dataone.org `redmine.dataone.org/projects/d1ops <https://redmine.dataone.org/projects/d1ops>`_
Metacat         `projects.ecoinformatics.org/ecoinfo/projects/metacat-5 <metacat-5>`_.
MetacatUI       `github.com/NCEAS/metacatui <ghmetacatui>`_ and 
                `projects.ecoinformatics.org/ecoinfo/projects/metacatui <metacatui>`_
=============== ============= 

.. _metacat-5: https://projects.ecoinformatics.org/ecoinfo/projects/metacat-5
.. _ghmetacatui: https://github.com/NCEAS/metacatui/issues
.. _metacatui: https://projects.ecoinformatics.org/ecoinfo/projects/metacatui


Redmine.dataone.org
-------------------

Redmine is currently setup on an Ubuntu 16.04 server running at UNM. The
installation uses the redmine distribution available from the standard Ubuntu
``apt`` repositories. Redmine is using a Postgresql database, converted from
the previous MySQL installation using pgloader_. Details of the installation
can be found at `redmine.dataone.org/admin/info
<https://redmine.dataone.org/admin/info>`_ which as of 2018-01-02 provides::

  Environment:
    Redmine version                3.2.1.stable
    Ruby version                   2.3.1-p112 (2016-04-26) [x86_64-linux-gnu]
    Rails version                  4.2.6
    Environment                    production
    Database adapter               PostgreSQL
  SCM:
    Subversion                     1.9.3
    Git                            2.7.4
    Filesystem                     
  Redmine plugins:
    clipboard_image_paste          1.12
    plantuml                       0.5.1
    redmine_checklists             3.1.10
    redmine_custom_css             0.1.6
    redmine_wiki_extensions        0.7.0
    redmine_wiki_lists             0.0.7
    scrum                          0.18.0


.. _pgloader: https://pgloader.io/


Upgrade Notes, redmine 2.6 -> 3.2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

   These notes are not relevant to general use of redmine, but are kept here for future reference.

The old version of redmine, running on Ubuntu 14.04 with MySQL::

  Environment:
    Redmine version                2.6.1.stable
    Ruby version                   2.0.0-p598 (2014-11-13) [x86_64-linux]
    Rails version                  3.2.21
    Environment                    production
    Database adapter               Mysql2
  SCM:
    Subversion                     1.8.8
    Git                            1.9.1
    Filesystem                     
  Redmine plugins:
    redmine_checklists             3.1.5
    redmine_questions              0.0.7
    redmine_wiki_extensions        0.6.5
    redmine_wiki_lists             0.0.3


On Ubuntu 16.04, latest maintained redmine is::

  $apt-cache showpkg redmine
  Package: redmine
  Versions:
  3.2.1-2 (/var/lib/apt/lists/us.archive.ubuntu.com_ubuntu_dists_xenial_universe_binary-amd64_Packages) (/var/lib/apt/lists/us.archive.ubuntu.com_ubuntu_dists_xenial_universe_binary-i386_Packages)
   Description Language:
                   File: /var/lib/apt/lists/us.archive.ubuntu.com_ubuntu_dists_xenial_universe_binary-amd64_Packages
                    MD5: 3a216a1439e1b07aad3aecd0c613d53b
   Description Language: en
                   File: /var/lib/apt/lists/us.archive.ubuntu.com_ubuntu_dists_xenial_universe_i18n_Translation-en
                    MD5: 3a216a1439e1b07aad3aecd0c613d53b


  Reverse Depends:
    redmine-plugin-custom-css,redmine 2.3.1~
    redmine-sqlite,redmine 3.2.1-2
    redmine-plugin-recaptcha,redmine 2.0.0
    redmine-plugin-pretend,redmine
    redmine-plugin-pretend,redmine 2.3.1~
    redmine-plugin-local-avatars,redmine
    redmine-plugin-local-avatars,redmine 2.3.1~
    redmine-plugin-custom-css,redmine
    redmine-mysql,redmine 3.2.1-2
    redmine-pgsql,redmine 3.2.1-2
  Dependencies:
  3.2.1-2 - debconf (0 (null)) dbconfig-common (0 (null)) redmine-sqlite (16 (null)) redmine-mysql (16 (null)) redmine-pgsql (0 (null)) ruby (16 (null)) ruby-interpreter (0 (null)) ruby-actionpack-action-caching (0 (null)) ruby-actionpack-xml-parser (0 (null)) ruby-awesome-nested-set (0 (null)) ruby-bundler (0 (null)) ruby-coderay (2 1.0.6) ruby-i18n (2 0.6.9-1~) ruby-jquery-rails (2 4.0.5) ruby-mime-types (2 1.25) ruby-net-ldap (2 0.3.1) ruby-openid (0 (null)) ruby-protected-attributes (0 (null)) ruby-rack (2 1.4.5~) ruby-rack-openid (0 (null)) ruby-rails (2 2:4.2.5) ruby-rails-observers (0 (null)) ruby-rbpdf (0 (null)) ruby-redcarpet (0 (null)) ruby-request-store (0 (null)) ruby-rmagick (0 (null)) ruby-roadie-rails (0 (null)) debconf (18 0.5) debconf-2.0 (0 (null)) redmine-plugin-botsfilter (1 1.02-2) redmine-plugin-recaptcha (1 0.1.0+git20121018) passenger (0 (null)) bzr (0 (null)) cvs (0 (null)) darcs (0 (null)) git (0 (null)) mercurial (0 (null)) ruby-fcgi (0 (null)) subversion (0 (null))
  Provides:
  3.2.1-2 -
  Reverse Provides:


Plan:

1. Create new server, ubuntu 16.04
  
   Created at UNM CIT, 8GB RAM, 4 CPU, 1TB disk. VM is d1-redmine5.dataone.org
   running on 64.106.40.38

2. Update, install mariadb-server, redmine via apt

   ::

     sudo apt-get install mariadb-server
     sudo apt-get install apache2
     sudo a2enmod ssl
     sudo a2enmod headers
     sudo a2ensite default-ssl
     sudo apt-get install passenger
     sudo apt-get install libapache2-mod-passenger
     sudo chown -R www-data:www-data /usr/share/redmine/public/plugin_assets
     sudo apt-get install imagemagick
     sudo apt-get install libmagickwand-dev
     sudo apt-get install ruby-rmagick
     sudo ufw allow 443

3. Make redmine readonly
4. Copy across attachments, mysql database dump, load database
5. Upgrade the database
6. Check operations
7. Migrate database to Postgresql
8. Verify operation
9. Install plugins
10. Switch DNS, make new redmine the current one

Plugins to install:

* scrum https://redmine.ociotec.com/projects/redmine-plugin-scrum
* redmine_checklists (free version) https://www.redmineup.com/pages/plugins/checklists
* Clipboard_image_paste http://www.redmine.org/plugins/clipboard_image_paste
* redmine_custom_css http://www.redmine.org/plugins/redmine_custom_css
* redmine_wiki_extensions http://www.redmine.org/plugins/redmine_wiki_extensions
* redmine_wiki_lists http://www.redmine.org/plugins/redmine_wiki_lists


Needed to adjust permissions to allow bundler to run without root (running
with root really messes things up). Some help here:
https://www.redmineup.com/pages/help/installation/how-to-install-redmine-
plugins-from-packages

In ``/usr/share/redmine``::

  chmod -R g+w public/plugin_assets
  sudo chmod -R g+w public/plugin_assets
  sudo chmod -R g+w tmp
  chown -R www-data:www-data db
  sudo chmod -R g+w www-data db
  sudo chmod -R g+w  db


::
  cd /usr/share/redmine
  bundle install --without development test
  bundle exec rake redmine:plugins:migrate --trace NAME=redhopper RAILS_ENV=production

Transferred to Postgresql using ``pgloader``::

  pgloader mysql://redmine:<<password>>@localhost/redmine_default pgsql:///redmine_default

After the transfer, needed to adjust table etc ownership::

  for tbl in `psql -qAt -c "select tablename from pg_tables where schemaname = 'public';" redmine_default` ; do  psql -c "alter table \"$tbl\" owner to redmine" redmine_default ; done

  for tbl in `psql -qAt -c "select sequence_name from information_schema.sequences where sequence_schema = 'public';" redmine_default` ; do  psql -c "alter table \"$tbl\" owner to redmine" redmine_default ; done

  for tbl in `psql -qAt -c "select table_name from information_schema.views where table_schema = 'public';" redmine_default` ; do  psql -c "alter table \"$tbl\" owner to redmine" redmine_default ; done

and set defaults for new objects::

  alter database redmine_default owner to redmine;
  GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO redmine;
  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO redmine;
  GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO redmine;
  alter default privileges grant all on functions to redmine;
  alter default privileges grant all on sequences to redmine;
  alter default privileges grant all on tables to redmine;


Installed scrum plugin from https://redmine.ociotec.com/projects/redmine-plugin-scrum/wiki





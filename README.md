# gitrtc

## rtc component to git repository migration tool, with Django framework

## Credits: https://github.com/rtcTo/rtc2git

## Progress
  - The tool is good for stream branching determine
  - The tool is good for verification after a component was migrated to git repository
  - The tool is good for the actual migration

## Requirements
  - SCM tools (recommend lscm for performance, tune java heap size to 3G+ if you have large amount of changesets in streams)
  - python3 + Django + django-mptt + docutils
  - mysql + mysqlclient (optional, if your component has 10K+ changesets for performance consideration)
  - use ubuntu 14.04 / 16.04 x64 when doing the migration, with scmtools and IBM jdk 1.8
  
## Tested on
  - MacOs 10.12
  - ubuntu 14.04 (best)
  - RHEL 6
  
## Steps
  1. install scmtools and login with proper account as the alias rtc
    * lscm logout -r rtc
    * lscm login -r https://rtc/url -u your_account -P your_password -n rtc -c
    * lscm list connections  (you should see the line with something including repo/url and your_account)
    * lscm help  (see help information)
  2. install python3
  3. install python3 modules
    * pip3 install Django django-mptt docutils
    * pip3 install mysqlclient (if select to use mysql database)
  4. fork, clone and configure the tool
    * edit local_settings.py, you can specify your rtc information to automate login and relogin
    * edit local_settings.py to decide using sqlite or mysql for database backend.
  5. run the tool:
    * ./djangoapp.py --component component_name --streambase your_trunk_stream_for_the_component [--infoinit | --infoshow | --infoupdate | --inforeport | --infoverify | --migrate] [other options]
      * --infoinit (run only once, you should keep using fake component like 'init' and fake streambase like 'init_trunk')
        * retrieve all of your project areas
        * retrieve their related streams
        * retrieve components for each stream
        * usually you only need to do this once, result will be saved as rtc/fixtures/infoinit.json and will be loaded when you process other components
        * you only need to update this when you add/remove streams or modified components in streams
      * --infoshow [--streams[id1,id2,]] [--writehistory]
        * list streams with their ids that you can specify in options like --streams
        * --streams [id1,id2,]
          * show informations to a subset of streams
        * --writehistory
          * write changeset history of streams 
      * --infoupdate
        * list all of the baselines for the component
        * for each stream containing the component, do the following with streambase the first one to process
          * list and create tree of changeset for the stream (if show history return 1000 changeses(lscm limit), create History/history_stream_name file; we can not use compare here since there is squence differences)
          * list baselines with the corresponding changesets associated
          * determine branching point against streambase (you may need to do further compare for branches with common branching point on trunk, with --branchfurther --streamparent)
        * you can pickup new delivered changesets with --incremental
        * you can do a lightweight analysis to determine branching information with --shortcut_analyze
      * --inforeport [--withbaselines] [--withchangesets] [--streams [id1,id2,]] [--levelrange]
        * report rtc information and component specific numbers
          * --withchangesets
          show changeset information on branching points and ending points
          * --withbaselines
          show baseline information, help
          * --streams [id1,id2,...]
          limit the streams to show in the report if you have too many or you only interest in some of them
          * --levelrange [0,1000] --levelinterval 10
          used when --withchangesets
      * --infoverify [--recordpath /path/to/records]
        * update internals to pick up database changes without --recordpath parameter
        * you need modify to fit your case
        * the recordpath is the location of the files with changeset uuid <-> git commitid information 
      * --migrate 
        * migrate only the trunk (--streambase) by default
        * you can migrate any stream using --streams [stread_id]
        * you can try to migrate all streams with --allstreams
        * you can use --incremental to pickup recently delivered changesets

## Examples
  1. ./djangoapp.py --component init --streambase init_trunk --infoinit  (only once)
  2. ./djangoapp.py --component yarn --streambase yarn_trunk --infoupdate
    1. ./djangoapp.py --component yarn --streambase yarn_trunk --infoupdate --branchfuther --streamparent yarn_IOP_working
  3. ./djangoapp.py --component yarn --streambase yarn_trunk --infoverify
  4. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport
    1. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport --withbaselines
    2. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport --withchangesets
    3. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport --withbaselines --withchangesets --streams [3,5,7]
  5. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate
    1. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate --streams [200]
    2. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate --incremental
    3. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate --allstreams
